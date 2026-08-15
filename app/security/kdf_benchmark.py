"""Benchmark local e reproduzível dos parâmetros Argon2id."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from statistics import median
from time import perf_counter

from app.security.kdf import KDFParameters, derive_key, generate_salt


@dataclass(frozen=True, slots=True)
class KDFBenchmarkResult:
    runs: int
    minimum_ms: float
    median_ms: float
    maximum_ms: float
    time_cost: int
    memory_cost_kib: int
    parallelism: int

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def benchmark_kdf(
    parameters: KDFParameters | None = None,
    *,
    runs: int = 5,
) -> KDFBenchmarkResult:
    """Mede derivações com senha e salt fictícios, sem acessar nenhum cofre."""
    if runs < 1 or runs > 50:
        raise ValueError("O benchmark deve executar entre 1 e 50 medições.")
    selected = parameters or KDFParameters()
    sample_phrase = "benchmark-keyciphra-frase-ficticia"
    salt = generate_salt()

    # Aquecimento evita incluir o carregamento inicial da biblioteca na mediana.
    derive_key(sample_phrase, salt, selected)
    durations: list[float] = []
    for _ in range(runs):
        started = perf_counter()
        derive_key(sample_phrase, salt, selected)
        durations.append((perf_counter() - started) * 1_000)

    return KDFBenchmarkResult(
        runs=runs,
        minimum_ms=round(min(durations), 2),
        median_ms=round(median(durations), 2),
        maximum_ms=round(max(durations), 2),
        time_cost=selected.time_cost,
        memory_cost_kib=selected.memory_cost_kib,
        parallelism=selected.parallelism,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Mede os parâmetros Argon2id do KeyCiphra.")
    parser.add_argument("--runs", type=int, default=5, help="Quantidade de medições (1–50).")
    arguments = parser.parse_args()
    result = benchmark_kdf(runs=arguments.runs)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
