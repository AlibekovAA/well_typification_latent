from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionPool(nn.Module):
    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.attn = nn.Linear(hidden_size, 1)

    def forward(self, seq_out: torch.Tensor) -> torch.Tensor:
        weights: torch.Tensor = torch.softmax(self.attn(seq_out), dim=1)
        return (seq_out * weights).sum(dim=1)


class RNNAutoencoder(nn.Module):
    def __init__(
        self,
        rnn_cls: type[nn.Module],
        input_dim: int,
        hidden_size: int,
        latent_dim: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.is_lstm = rnn_cls is nn.LSTM
        eff_dropout = dropout if num_layers > 1 else 0.0

        self.encoder_rnn = rnn_cls(
            input_dim,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=eff_dropout,
            bidirectional=True,
        )
        self.attn_pool = AttentionPool(hidden_size * 2)
        self.encoder_fc = nn.Linear(hidden_size * 2, latent_dim)

        self.decoder_fc = nn.Linear(latent_dim, hidden_size * num_layers)
        self.decoder_rnn = rnn_cls(
            input_dim,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=eff_dropout,
        )
        self.output_fc = nn.Linear(hidden_size, input_dim)

        self.apply(self._init_weights)

    def _init_weights(self, m: nn.Module) -> None:
        if isinstance(m, (nn.Linear, nn.Conv1d)):
            nn.init.xavier_uniform_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, (nn.GRU, nn.LSTM)):
            for name, param in m.named_parameters():
                if "weight" in name:
                    nn.init.orthogonal_(param)
                elif "bias" in name:
                    nn.init.zeros_(param)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.encoder_rnn(x)
        pooled = cast(torch.Tensor, self.attn_pool(out))
        return cast(torch.Tensor, self.encoder_fc(pooled))

    def _init_hidden(self, z: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor] | torch.Tensor:
        h = cast(
            torch.Tensor,
            self.decoder_fc(z).view(z.size(0), self.num_layers, self.hidden_size).permute(1, 0, 2).contiguous(),
        )
        return (h, torch.zeros_like(h)) if self.is_lstm else h

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        x_shifted = torch.cat([x[:, :1, :], x[:, :-1, :]], dim=1)
        out, _ = self.decoder_rnn(x_shifted, self._init_hidden(z))
        return cast(torch.Tensor, self.output_fc(out)), z


class GRUAutoencoder(RNNAutoencoder):
    def __init__(
        self,
        input_dim: int,
        hidden_size: int,
        latent_dim: int,
        num_layers: int,
        dropout: float,
    ) -> None:
        super().__init__(nn.GRU, input_dim, hidden_size, latent_dim, num_layers, dropout)


class CausalConv1d(nn.Conv1d):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int) -> None:
        super().__init__(in_channels, out_channels, kernel_size, padding=0, dilation=dilation)
        self._causal_pad = (kernel_size - 1) * dilation

    def forward(self, input: torch.Tensor) -> torch.Tensor:
        return super().forward(F.pad(input, (self._causal_pad, 0)))


class TemporalBlock(nn.Module):
    def __init__(
        self,
        n_in: int,
        n_out: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.net = nn.Sequential(
            CausalConv1d(n_in, n_out, kernel_size, dilation),
            nn.BatchNorm1d(n_out),
            nn.GELU(),
            nn.Dropout(dropout),
            CausalConv1d(n_out, n_out, kernel_size, dilation),
            nn.BatchNorm1d(n_out),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.downsample: nn.Module = nn.Conv1d(n_in, n_out, 1) if n_in != n_out else nn.Identity()
        self.act = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, self.act(self.net(x) + self.downsample(x)))


def _build_tcn_encoder(
    input_dim: int,
    hidden_size: int,
    num_layers: int,
    kernel_size: int,
    dilation_base: int,
    dropout: float,
) -> nn.Sequential:
    return nn.Sequential(
        *[
            TemporalBlock(
                input_dim if i == 0 else hidden_size,
                hidden_size,
                kernel_size,
                dilation_base**i,
                dropout,
            )
            for i in range(num_layers)
        ]
    )


class TCNAutoencoder(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_size: int,
        latent_dim: int,
        num_layers: int,
        kernel_size: int,
        dilation_base: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.encoder = _build_tcn_encoder(input_dim, hidden_size, num_layers, kernel_size, dilation_base, dropout)
        self.attn_pool = AttentionPool(hidden_size)
        self.bottleneck = nn.Linear(hidden_size, latent_dim)
        self.decoder_bridge = nn.Sequential(nn.Linear(latent_dim, hidden_size), nn.GELU())
        self.decoder = _build_tcn_encoder(hidden_size, hidden_size, num_layers, kernel_size, dilation_base, dropout)
        self.input_proj = nn.Conv1d(input_dim, hidden_size, kernel_size=1)
        self.output_conv = nn.Conv1d(hidden_size, input_dim, 1)

        self.apply(self._init_weights)

    def _init_weights(self, m: nn.Module) -> None:
        if isinstance(m, (nn.Linear, nn.Conv1d)):
            nn.init.xavier_uniform_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        enc = cast(torch.Tensor, self.encoder(x.transpose(1, 2)))
        enc = enc.transpose(1, 2)
        pooled = cast(torch.Tensor, self.attn_pool(enc))
        return cast(torch.Tensor, self.bottleneck(pooled))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        x_shifted = torch.cat([x[:, :1, :], x[:, :-1, :]], dim=1)
        h = self.decoder_bridge(z).unsqueeze(-1).expand(-1, -1, x.size(1))
        x_proj = self.input_proj(x_shifted.transpose(1, 2))
        h = h + x_proj

        decoded = self.decoder(h)
        recon = self.output_conv(decoded).transpose(1, 2)
        return recon, z


class HybridAutoencoder(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_size: int,
        latent_dim: int,
        num_layers: int,
        kernel_size: int,
        dilation_base: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.encoder = _build_tcn_encoder(input_dim, hidden_size, num_layers, kernel_size, dilation_base, dropout)
        self.attn_pool = AttentionPool(hidden_size)
        self.bottleneck = nn.Linear(hidden_size, latent_dim)

        self.decoder_fc = nn.Linear(latent_dim, hidden_size * num_layers)
        self.decoder_gru = nn.GRU(
            input_dim,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.output_fc = nn.Linear(hidden_size, input_dim)

        self.apply(self._init_weights)

    def _init_weights(self, m: nn.Module) -> None:
        if isinstance(m, (nn.Linear, nn.Conv1d)):
            nn.init.xavier_uniform_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, (nn.GRU, nn.LSTM)):
            for name, param in m.named_parameters():
                if "weight" in name:
                    nn.init.orthogonal_(param)
                elif "bias" in name:
                    nn.init.zeros_(param)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        h = cast(torch.Tensor, self.encoder(x.transpose(1, 2)))
        pooled = cast(torch.Tensor, self.attn_pool(h.transpose(1, 2)))
        return cast(torch.Tensor, self.bottleneck(pooled))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        h0 = (
            cast(torch.Tensor, self.decoder_fc(z))
            .view(z.size(0), self.num_layers, self.hidden_size)
            .permute(1, 0, 2)
            .contiguous()
        )
        x_shifted = torch.cat([x[:, :1, :], x[:, :-1, :]], dim=1)
        out, _ = self.decoder_gru(x_shifted, h0)
        return cast(torch.Tensor, self.output_fc(out)), z


def build_model(
    arch_name: str,
    input_dim: int,
    hidden_size: int,
    latent_dim: int,
    num_layers: int,
    kernel_size: int,
    dilation_base: int,
    dropout: float,
) -> nn.Module:
    if arch_name == "GRU":
        return GRUAutoencoder(input_dim, hidden_size, latent_dim, num_layers, dropout)
    if arch_name == "TCN":
        return TCNAutoencoder(input_dim, hidden_size, latent_dim, num_layers, kernel_size, dilation_base, dropout)
    if arch_name == "Hybrid":
        return HybridAutoencoder(input_dim, hidden_size, latent_dim, num_layers, kernel_size, dilation_base, dropout)
    raise ValueError(f"Неизвестная архитектура: {arch_name!r}. Ожидается: 'GRU', 'TCN', 'Hybrid'.")
