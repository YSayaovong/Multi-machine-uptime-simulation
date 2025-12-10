"""
Multi-Machine Uptime & Bottleneck Simulator - Production Version

- Models multiple stations in a production line (serial flow)
- Each station has:
    * Mean cycle time
    * MTBF (mean time between failures)
    * MTTR (mean time to repair)
    * Parallel units (machines in parallel)
- Monte Carlo simulation over a fixed time horizon (e.g., 8h shift)
- Outputs:
    * Distribution of line throughput
    * Bottleneck probability per station
    * Average downtime per station
    * Plots saved as PNGs
"""

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Dict


# -------------------------------------------------
# Data Models
# -------------------------------------------------

@dataclass
class StationConfig:
    name: str
    mean_cycle_time_sec: float   # average processing time per unit per machine
    mtbf_hours: float            # mean time between failures (per machine)
    mttr_hours: float            # mean time to repair (per machine)
    parallel_units: int = 1      # number of identical machines in parallel


@dataclass
class StationResult:
    name: str
    total_busy_time: float       # [sec]
    total_downtime: float        # [sec]
    total_units: int             # units produced across all parallel machines


class MultiMachineLineSimulator:
    def __init__(self, stations: List[StationConfig], horizon_hours: float):
        self.stations = stations
        self.horizon_hours = horizon_hours
        self.horizon_sec = horizon_hours * 3600.0

    # -----------------------------
    # Single Station Simulation
    # -----------------------------
    def _simulate_station_units(self, cfg: StationConfig, rng: np.random.Generator) -> StationResult:
        """
        Simulates one station with parallel machines over the horizon.
        Assumes each machine is always starved/blocked-free (line capacity analysis).
        """
        total_busy = 0.0
        total_down = 0.0
        total_units = 0

        mtbf_sec = cfg.mtbf_hours * 3600.0
        mttr_sec = cfg.mttr_hours * 3600.0

        for _ in range(cfg.parallel_units):
            t = 0.0
            busy = 0.0
            down = 0.0
            units = 0

            while t < self.horizon_sec:
                # Uptime period (machine available, always has work)
                up_time = rng.exponential(mtbf_sec)
                if t + up_time > self.horizon_sec:
                    up_time = self.horizon_sec - t

                if cfg.mean_cycle_time_sec > 0:
                    possible_units = int(up_time // cfg.mean_cycle_time_sec)
                    produced_time = possible_units * cfg.mean_cycle_time_sec
                else:
                    possible_units = 0
                    produced_time = 0.0

                busy += produced_time
                t += up_time
                units += possible_units

                if t >= self.horizon_sec:
                    break

                # Failure + repair
                repair_time = rng.exponential(mttr_sec)
                if t + repair_time > self.horizon_sec:
                    repair_time = self.horizon_sec - t
                down += repair_time
                t += repair_time

            total_busy += busy
            total_down += down
            total_units += units

        return StationResult(
            name=cfg.name,
            total_busy_time=total_busy,
            total_downtime=total_down,
            total_units=total_units,
        )

    # -----------------------------
    # Monte Carlo Over the Line
    # -----------------------------
    def run_monte_carlo(self, runs: int = 500, seed: int = 42):
        rng = np.random.default_rng(seed)

        line_throughputs = []
        bottleneck_counts: Dict[str, int] = {cfg.name: 0 for cfg in self.stations}
        station_busy_time = {cfg.name: 0.0 for cfg in self.stations}
        station_downtime = {cfg.name: 0.0 for cfg in self.stations}
        station_units = {cfg.name: 0.0 for cfg in self.stations}

        for _ in range(runs):
            results = []
            for cfg in self.stations:
                res = self._simulate_station_units(cfg, rng)
                results.append(res)
                station_busy_time[cfg.name] += res.total_busy_time
                station_downtime[cfg.name] += res.total_downtime
                station_units[cfg.name] += res.total_units

            # line throughput = limited by station with fewest units
            units_per_station = [r.total_units for r in results]
            line_throughput = min(units_per_station)
            line_throughputs.append(line_throughput)

            # bottleneck station(s) = those with min units
            min_units = min(units_per_station)
            for r in results:
                if r.total_units == min_units:
                    bottleneck_counts[r.name] += 1

        summary = {
            "line_throughputs": np.array(line_throughputs),
            "bottleneck_counts": bottleneck_counts,
            "station_busy_time": station_busy_time,
            "station_downtime": station_downtime,
            "station_units": station_units,
        }
        return summary


# -------------------------------------------------
# Example Factory Scenario
# -------------------------------------------------

def example_usage():
    # Example line – adjust names and numbers to match your domain
    stations = [
        StationConfig(
            name="Core Winding",
            mean_cycle_time_sec=45.0,
            mtbf_hours=120.0,
            mttr_hours=1.0,
            parallel_units=2,
        ),
        StationConfig(
            name="Coil Assembly",
            mean_cycle_time_sec=60.0,
            mtbf_hours=90.0,
            mttr_hours=1.5,
            parallel_units=1,
        ),
        StationConfig(
            name="Tank Fabrication",
            mean_cycle_time_sec=80.0,
            mtbf_hours=150.0,
            mttr_hours=2.0,
            parallel_units=1,
        ),
        StationConfig(
            name="Final Assembly",
            mean_cycle_time_sec=70.0,
            mtbf_hours=100.0,
            mttr_hours=1.0,
            parallel_units=2,
        ),
    ]

    horizon_hours = 8.0  # e.g., one shift
    sim = MultiMachineLineSimulator(stations, horizon_hours=horizon_hours)
    summary = sim.run_monte_carlo(runs=500, seed=123)

    line_throughputs = summary["line_throughputs"]
    bottleneck_counts = summary["bottleneck_counts"]
    station_busy_time = summary["station_busy_time"]
    station_downtime = summary["station_downtime"]

    print("=== LINE THROUGHPUT SUMMARY ===")
    print(f"Mean throughput per {horizon_hours:.1f}h = {line_throughputs.mean():.1f} units")
    print(f"5th percentile                = {np.percentile(line_throughputs, 5):.1f} units")
    print(f"95th percentile               = {np.percentile(line_throughputs, 95):.1f} units")

    print("\n=== BOTTLENECK PROBABILITY ===")
    total_runs = len(line_throughputs)
    station_names = [cfg.name for cfg in stations]
    for name in station_names:
        count = bottleneck_counts[name]
        p = count / total_runs
        print(f"{name:20s}: {p*100:5.1f} % of runs")

    # -------------------------------------------------
    # Plots
    # -------------------------------------------------

    # Throughput distribution
    plt.figure()
    plt.hist(line_throughputs, bins=30, density=True)
    plt.xlabel(f"Units produced in {horizon_hours:.1f} hours")
    plt.ylabel("Probability density")
    plt.title("Line Throughput Distribution")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("line_throughput_distribution.png", dpi=150)
    plt.close()

    # Bottleneck probability bar chart
    probs = [bottleneck_counts[n] / total_runs for n in station_names]
    plt.figure()
    plt.bar(station_names, probs)
    plt.ylabel("Bottleneck probability")
    plt.title("Bottleneck Likelihood by Station")
    plt.xticks(rotation=20, ha="right")
    plt.grid(axis="y")
    plt.tight_layout()
    plt.savefig("bottleneck_probability.png", dpi=150)
    plt.close()

    # Average downtime per station
    avg_downtime_hours = [station_downtime[n] / total_runs / 3600.0 for n in station_names]
    plt.figure()
    plt.bar(station_names, avg_downtime_hours)
    plt.ylabel("Avg downtime per run [hours]")
    plt.title("Average Downtime by Station")
    plt.xticks(rotation=20, ha="right")
    plt.grid(axis="y")
    plt.tight_layout()
    plt.savefig("station_downtime.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    example_usage()
