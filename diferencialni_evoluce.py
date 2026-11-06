
import csv
import math
import random
import statistics
from pathlib import Path

import matplotlib.pyplot as plt


def sphere(individual):
    return sum(x * x for x in individual)


def rosenbrock(individual):
    return sum(
        100 * (next_x - x * x) ** 2 + (1 - x) ** 2
        for x, next_x in zip(individual, individual[1:])
    )


def schwefel(individual):
    return 418.9828872724338 * len(individual) - sum(
        x * math.sin(math.sqrt(abs(x))) for x in individual
    )


def create_individual(dimension, low, high):
    return [random.uniform(low, high) for _ in range(dimension)]


def pick_indexes(population_size, current, count):
    indexes = random.sample(range(population_size), count + 1)
    return [index for index in indexes if index != current][:count]


def rand_1(population, current, best_index, f):
    r1, r2, r3 = pick_indexes(len(population), current, 3)
    return [
        a + f * (b - c)
        for a, b, c in zip(population[r1], population[r2], population[r3])
    ]


def best_1(population, current, best_index, f):
    r1, r2 = pick_indexes(len(population), current, 2)
    return [
        best + f * (a - b)
        for best, a, b in zip(population[best_index], population[r1], population[r2])
    ]


def mutate(population, current, best_index, f, mutation_type):
    if mutation_type == "rand_1":
        return rand_1(population, current, best_index, f)
    if mutation_type == "best_1":
        return best_1(population, current, best_index, f)
    raise ValueError("Unknown mutation type")


def binomial_crossover(target, mutant, cr):
    forced_index = random.randrange(len(target))
    return [
        mutant[i] if random.random() < cr or i == forced_index else target[i]
        for i in range(len(target))
    ]


def repair(individual, low, high):
    return [min(max(x, low), high) for x in individual]


def differential_evolution(
    dimension,
    fitness_function,
    low,
    high,
    max_evaluations,
    population_size=50,
    f=0.5,
    cr=0.8,
    mutation_type="rand_1",
    self_adaptive=False,
    tau1=0.1,
    tau2=0.1,
    f_low=0.1,
    f_high=0.9
):
    if dimension < 2:
        raise ValueError("Dimension is too small")
    if population_size < 4 or population_size > max_evaluations:
        raise ValueError("Invalid population size")
    if not 0 <= cr <= 1 or not 0 <= tau1 <= 1 or not 0 <= tau2 <= 1:
        raise ValueError("Probabilities must be between 0 and 1")
    if not 0 < f_low <= f <= f_high:
        raise ValueError("F must be inside its range")

    population = [create_individual(dimension, low, high) for _ in range(population_size)]
    f_values = [f] * population_size
    cr_values = [cr] * population_size
    fitness_values = []
    convergence = []
    best_fitness = float("inf")
    evaluations = 0

    for individual in population:
        fitness = fitness_function(individual)
        fitness_values.append(fitness)
        evaluations += 1
        best_fitness = min(best_fitness, fitness)
        convergence.append(best_fitness)

    while evaluations < max_evaluations:
        best_index = min(range(population_size), key=lambda i: fitness_values[i])
        new_population = population.copy()
        new_fitness_values = fitness_values.copy()
        new_f_values = f_values.copy()
        new_cr_values = cr_values.copy()

        for i in range(population_size):
            if evaluations >= max_evaluations:
                break

            trial_f = f_values[i]
            trial_cr = cr_values[i]
            if self_adaptive:
                if random.random() < tau1:
                    trial_f = random.uniform(f_low, f_high)
                if random.random() < tau2:
                    trial_cr = random.random()

            mutant = mutate(population, i, best_index, trial_f, mutation_type)
            trial = repair(binomial_crossover(population[i], mutant, trial_cr), low, high)

            fitness = fitness_function(trial)
            evaluations += 1
            best_fitness = min(best_fitness, fitness)
            convergence.append(best_fitness)

            if fitness <= fitness_values[i]:
                new_population[i] = trial
                new_fitness_values[i] = fitness
                new_f_values[i] = trial_f
                new_cr_values[i] = trial_cr

        population = new_population
        fitness_values = new_fitness_values
        f_values = new_f_values
        cr_values = new_cr_values

    return best_fitness, convergence


def run_experiment(problem_index, problem, dimension, max_evaluations, runs, settings, target):
    problem_name, fitness_function, low, high = problem
    final_results = []
    all_convergences = []
    first_optimum_evaluations = []

    for run in range(runs):
        random.seed(1000 + run + dimension * 10 + problem_index * 100000)
        best, convergence = differential_evolution(
            dimension=dimension,
            fitness_function=fitness_function,
            low=low,
            high=high,
            max_evaluations=max_evaluations,
            **settings
        )

        final_results.append(best)
        all_convergences.append(convergence)
        if best <= target:
            first_optimum_evaluations.append(
                next(i for i, value in enumerate(convergence, start=1) if value <= target)
            )

    convergence_quartiles = [
        statistics.quantiles(values, n=4, method="inclusive")
        for values in zip(*all_convergences)
    ]
    stats = {
        "best": min(final_results),
        "worst": max(final_results),
        "mean": statistics.mean(final_results),
        "median": statistics.median(final_results),
        "std": statistics.stdev(final_results),
        "optimal_runs": len(first_optimum_evaluations),
        "avg_optimum_evaluations": (
            statistics.mean(first_optimum_evaluations)
            if first_optimum_evaluations else None
        )
    }
    return stats, convergence_quartiles


def draw_graph(problem_name, dimension, curves, target, output_dir, file_suffix=""):
    plt.figure(figsize=(11, 6))

    for label, quartiles in curves.items():
        evaluations = range(1, len(quartiles) + 1)
        lower, median, upper = zip(*quartiles)
        line, = plt.plot(evaluations, median, label=label)
        plt.fill_between(evaluations, lower, upper, color=line.get_color(), alpha=0.15, linewidth=0)

    plt.axhline(target, linestyle="--", color="gray", linewidth=1, label="Target (1e-8)")
    plt.yscale("log")
    plt.title(f"{problem_name} - Median Convergence - {dimension}D, {len(quartiles)} evaluations (10 runs, 25-75% band)")
    plt.xlabel("Fitness Evaluations")
    plt.ylabel("Best Fitness (median, log scale)")
    plt.legend(fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    file_name = output_dir / f"{problem_name}_{dimension}D{file_suffix}.png"
    plt.savefig(file_name, dpi=150)
    plt.close()
    print(f"Graph saved: {file_name}")


def run_group(problem_index, problem, dimension, max_evaluations, runs, experiments, base_settings, target):
    problem_name = problem[0]
    generations = max_evaluations // base_settings["population_size"]
    print(f"\n{'=' * 85}")
    print(f"{problem_name} - {dimension}D, {runs} runs, {max_evaluations} evaluations per run (~{generations} generations)")
    print(f"{'=' * 85}")
    print(f"{'Configuration':<18} {'Best':>10} {'Worst':>10} {'Mean':>10} {'Median':>10} {'Std':>10} {'Optimal':>8}")

    curves = {}
    group_rows = []

    for label, changes in experiments:
        settings = {**base_settings, **changes}
        stats, convergence_quartiles = run_experiment(
            problem_index, problem, dimension, max_evaluations, runs, settings, target
        )
        curves[label] = convergence_quartiles

        group_rows.append({
            "problem": problem_name,
            "dimension": dimension,
            "max_evaluations": max_evaluations,
            "configuration": label,
            **settings,
            **stats
        })

        print(
            f"{label:<18} {stats['best']:>10.3g} {stats['worst']:>10.3g} "
            f"{stats['mean']:>10.3g} {stats['median']:>10.3g} "
            f"{stats['std']:>10.3g} {stats['optimal_runs']:>5}/{runs}",
            flush=True
        )

    best = max(
        group_rows,
        key=lambda row: (
            -row["median"], row["optimal_runs"],
            -row["avg_optimum_evaluations"]
            if row["avg_optimum_evaluations"] is not None else float("-inf")
        )
    )
    print(f"Best configuration: {best['configuration']}")
    return group_rows, curves


def main():
    base_settings = {
        "population_size": 50,
        "f": 0.5,
        "cr": 0.8,
        "mutation_type": "rand_1",
        "self_adaptive": False
    }

    experiments = [
        ("Rand/1", {}),
        ("Best/1", {"mutation_type": "best_1"}),
        ("jDE", {"cr": 0.9, "self_adaptive": True})
    ]

    problems = [
        ("Sphere", sphere, -5.12, 5.12),
        ("Rosenbrock", rosenbrock, -2.048, 2.048),
        ("Schwefel", schwefel, -500.0, 500.0)
    ]
    dimensions = [10, 30, 100]
    runs = 10
    target = 1e-8
    output_dir = Path(__file__).resolve().parent / "de_results"
    output_dir.mkdir(exist_ok=True)
    summary_rows = []

    for problem_index, problem in enumerate(problems):
        for dimension in dimensions:
            group_rows, curves = run_group(
                problem_index, problem, dimension, 1000 * dimension,
                runs, experiments, base_settings, target
            )
            summary_rows += group_rows
            draw_graph(problem[0], dimension, curves, target, output_dir)

    control_rows, control_curves = run_group(
        1, problems[1], 10, 10000 * 10,
        runs, [experiments[0], experiments[2]], base_settings, target
    )
    summary_rows += control_rows
    draw_graph(problems[1][0], 10, control_curves, target, output_dir, file_suffix="_control")

    csv_file = output_dir / "summary.csv"
    with csv_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nResults saved to: {output_dir}")
    print(f"Summary saved to: {csv_file}")


if __name__ == "__main__":
    main()
