"""Genetic algorithm-based pipeline optimization framework."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple
import datetime
import json
import os
import random
import time
import uuid


class Gene:
    """A single gene representing an execution parameter."""

    def __init__(self, name: str, value: Any,
                 min_val: Optional[float] = None,
                 max_val: Optional[float] = None,
                 choices: Optional[List[Any]] = None) -> None:
        self.name = name
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.choices = choices

    def mutate(self, rate: float = 0.1) -> None:
        if random.random() > rate:
            return
        if self.choices:
            self.value = random.choice(self.choices)
        elif isinstance(self.value, float) and self.min_val is not None and self.max_val is not None:
            self.value = round(random.uniform(self.min_val, self.max_val), 4)
        elif isinstance(self.value, int) and self.min_val is not None and self.max_val is not None:
            self.value = random.randint(int(self.min_val), int(self.max_val))

    def copy(self) -> Gene:
        return Gene(self.name, self.value, self.min_val, self.max_val, self.choices)

    def to_dict(self) -> Dict[str, Any]:
        return {'name': self.name, 'value': self.value}


class Chromosome:
    """A candidate solution encoded as a list of genes."""

    def __init__(self, genes: Optional[List[Gene]] = None) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.genes = genes or []
        self.fitness: Optional[float] = None

    def mutate(self, rate: float = 0.1) -> None:
        for g in self.genes:
            g.mutate(rate)

    def copy(self) -> Chromosome:
        c = Chromosome([g.copy() for g in self.genes])
        c.fitness = self.fitness
        return c

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'genes': [g.to_dict() for g in self.genes],
            'fitness': self.fitness,
        }


class FitnessFunction:
    """Evaluate a chromosome's fitness (lower = better)."""

    def __init__(self, fn: Callable[[Dict[str, Any]], float]) -> None:
        self._fn = fn

    def evaluate(self, chromosome: Chromosome) -> float:
        params = {g.name: g.value for g in chromosome.genes}
        return self._fn(params)


class SelectionOperator:
    """Tournament selection for candidate promotion."""

    @staticmethod
    def tournament(population: List[Chromosome], tournament_size: int = 3) -> Chromosome:
        candidates = random.sample(population, min(tournament_size, len(population)))
        candidates.sort(key=lambda c: c.fitness if c.fitness is not None else float('inf'))
        return candidates[0]


class CrossoverOperator:
    """Single-point crossover between two parent chromosomes."""

    @staticmethod
    def single_point(parent_a: Chromosome, parent_b: Chromosome) -> Tuple[Chromosome, Chromosome]:
        if len(parent_a.genes) < 2:
            return parent_a.copy(), parent_b.copy()
        point = random.randint(1, len(parent_a.genes) - 1)
        child_a = Chromosome(parent_a.genes[:point] + parent_b.genes[point:])
        child_b = Chromosome(parent_b.genes[:point] + parent_a.genes[point:])
        return child_a, child_b


class Population:
    """Manage a population of chromosomes across generations."""

    def __init__(self, size: int = 20) -> None:
        self.size = size
        self.chromosomes: List[Chromosome] = []

    def initialize(self, gene_defs: List[Dict[str, Any]]) -> None:
        self.chromosomes = []
        for _ in range(self.size):
            genes = []
            for gd in gene_defs:
                if 'choices' in gd and gd['choices']:
                    value = random.choice(gd['choices'])
                elif 'min' in gd and 'max' in gd:
                    if gd.get('type') == int:
                        value = random.randint(int(gd['min']), int(gd['max']))
                    else:
                        value = round(random.uniform(gd['min'], gd['max']), 4)
                else:
                    value = gd.get('default', 0)
                genes.append(Gene(gd['name'], value, gd.get('min'), gd.get('max'), gd.get('choices')))
            self.chromosomes.append(Chromosome(genes))

    def best(self) -> Optional[Chromosome]:
        evaluated = [c for c in self.chromosomes if c.fitness is not None]
        if not evaluated:
            return None
        return min(evaluated, key=lambda c: c.fitness)

    def average_fitness(self) -> Optional[float]:
        evaluated = [c for c in self.chromosomes if c.fitness is not None]
        if not evaluated:
            return None
        return sum(c.fitness for c in evaluated) / len(evaluated)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'size': len(self.chromosomes),
            'best_fitness': self.best().fitness if self.best() else None,
            'avg_fitness': self.average_fitness(),
        }


class GeneticOptimizer:
    """Run genetic optimization with crossover, mutation, tournament, and elite preservation."""

    def __init__(self, fitness_fn: FitnessFunction,
                 gene_defs: List[Dict[str, Any]],
                 population_size: int = 20,
                 generations: int = 10,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.8,
                 elite_count: int = 2,
                 tournament_size: int = 3) -> None:
        self._fitness_fn = fitness_fn
        self._gene_defs = gene_defs
        self._population_size = population_size
        self._generations = generations
        self._mutation_rate = mutation_rate
        self._crossover_rate = crossover_rate
        self._elite_count = elite_count
        self._tournament_size = tournament_size
        self._population = Population(population_size)
        self._history: List[Dict[str, Any]] = []
        self._best_chromosome: Optional[Chromosome] = None

    def run(self) -> Chromosome:
        self._population.initialize(self._gene_defs)

        for gen in range(self._generations):
            for chrom in self._population.chromosomes:
                if chrom.fitness is None:
                    chrom.fitness = self._fitness_fn.evaluate(chrom)

            self._population.chromosomes.sort(key=lambda c: c.fitness if c.fitness is not None else float('inf'))

            best = self._population.best()
            if best and (self._best_chromosome is None or best.fitness < self._best_chromosome.fitness):
                self._best_chromosome = best.copy()

            record = {
                'generation': gen + 1,
                'best_fitness': best.fitness if best else None,
                'avg_fitness': self._population.average_fitness(),
            }
            self._history.append(record)

            if gen == self._generations - 1:
                break

            elites = [c.copy() for c in self._population.chromosomes[:self._elite_count]]

            next_gen: List[Chromosome] = []
            while len(next_gen) < self._population_size - self._elite_count:
                parent_a = SelectionOperator.tournament(self._population.chromosomes, self._tournament_size)
                parent_b = SelectionOperator.tournament(self._population.chromosomes, self._tournament_size)
                if random.random() < self._crossover_rate:
                    child_a, child_b = CrossoverOperator.single_point(parent_a, parent_b)
                else:
                    child_a, child_b = parent_a.copy(), parent_b.copy()
                child_a.mutate(self._mutation_rate)
                child_b.mutate(self._mutation_rate)
                next_gen.append(child_a)
                if len(next_gen) < self._population_size - self._elite_count:
                    next_gen.append(child_b)

            self._population.chromosomes = elites + next_gen[:self._population_size - self._elite_count]

        return self._best_chromosome or self._population.best()

    @property
    def history(self) -> List[Dict[str, Any]]:
        return self._history

    @property
    def best(self) -> Optional[Chromosome]:
        return self._best_chromosome


class GeneticOptimizationEngine:
    """Top-level genetic algorithm pipeline optimization framework."""

    def __init__(self) -> None:
        self._runs: List[Dict[str, Any]] = []

    def optimize(self, gene_defs: List[Dict[str, Any]],
                 fitness_fn: Callable[[Dict[str, Any]], float],
                 population_size: int = 20,
                 generations: int = 10,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.8,
                 elite_count: int = 2,
                 label: str = '') -> Chromosome:
        ff = FitnessFunction(fitness_fn)
        optimizer = GeneticOptimizer(
            ff, gene_defs, population_size, generations,
            mutation_rate, crossover_rate, elite_count,
        )
        start = time.perf_counter()
        result = optimizer.run()
        elapsed = time.perf_counter() - start

        run_record = {
            'run_id': uuid.uuid4().hex[:8],
            'label': label or f'run_{len(self._runs) + 1}',
            'generations': generations,
            'population_size': population_size,
            'elapsed_s': round(elapsed, 3),
            'best_fitness': result.fitness if result else None,
            'best_params': {g.name: g.value for g in result.genes} if result else {},
            'history': optimizer.history,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._runs.append(run_record)
        return result

    def run_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._runs[-limit:]

    def last_result(self) -> Optional[Dict[str, Any]]:
        return self._runs[-1] if self._runs else None

    def summary(self) -> Dict[str, Any]:
        return {
            'total_runs': len(self._runs),
            'last_best_fitness': self._runs[-1]['best_fitness'] if self._runs else None,
        }

    def report_text(self) -> str:
        s = self.summary()
        return (
            f'Genetic Optimizer Engine\n'
            f'  Runs: {s["total_runs"]}\n'
            f'  Best fitness: {s["last_best_fitness"]}'
        )

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        sp = os.path.join(dir, 'genetic_optimizer.json')
        with open(sp, 'w') as f:
            json.dump(self._runs[-5:] if self._runs else [], f, indent=2)
        paths.append(sp)
        return paths
