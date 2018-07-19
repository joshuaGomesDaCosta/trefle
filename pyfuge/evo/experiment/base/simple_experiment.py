import math
import random
from typing import Callable

import numpy as np
from deap import creator, base, tools, algorithms

from pyfuge.evo.dataset.pf_dataset import PFDataset
from pyfuge.evo.experiment.base.experiment import Experiment
from pyfuge.evo.helpers.fis_individual import FISIndividual


class SimpleEAExperiment(Experiment):
    """
    A class that performs an experiment using a simple EA (evolutionary
    algorithm) with DEAP library.
    """

    def __init__(self, dataset: PFDataset, fis_individual: FISIndividual,
                 fitness_func: Callable, **kwargs):
        super(SimpleEAExperiment, self).__init__(dataset, fis_individual,
                                                 fitness_func, **kwargs)

        target_length = self._fis_individual.ind_length()

        try:
            # Don't recreate creator classes if they already exist. See issue 41
            creator.FitnessMax
        except AttributeError:
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()

        toolbox.register("attr_bool", random.random)
        toolbox.register("individual", tools.initRepeat, creator.Individual,
                         toolbox.attr_bool, n=target_length)
        toolbox.register("population", tools.initRepeat, list,
                         toolbox.individual)

        def eval_ind(ind):
            y_pred_one_hot = self._fis_individual.predict(ind)
            y_true = np.argmax(self._dataset.y, axis=1)

            # TODO: do not threshold/binarize y_pred. Instead let the fitness
            # handle that otherwise we regression metrics are useless (even in
            # a classification problem)
            if y_pred_one_hot.shape[0] > 1:
                y_pred = np.argmax(y_pred_one_hot, axis=1)
            else:
                y_pred = np.round(y_pred_one_hot)

            fitness = self._fitness_func(y_true, y_pred)
            return fitness,  # DEAP expects a tuple for fitnesses

        toolbox.register("evaluate", eval_ind)
        toolbox.register("mate", tools.cxTwoPoint)
        toolbox.register("mutate", tools.mutShuffleIndexes,
                         indpb=1.0 / (10.0 * math.ceil(
                             math.log(target_length, 10)))),
        toolbox.register("select", tools.selTournament, tournsize=3)

        verbose = kwargs.pop("verbose", False)
        stats = self.setup_stats(verbose)

        N_POP = self._kwargs.get("N_POP") or 100
        population = toolbox.population(n=N_POP)

        NGEN = self._kwargs.get("N_GEN") or 10

        hof = tools.HallOfFame(self._kwargs.get("HOF") or 5)

        algorithms.eaSimple(population, toolbox, cxpb=0.8, mutpb=0.3, ngen=NGEN,
                            halloffame=hof, stats=stats, verbose=verbose)
        self._top_n = tools.selBest(population, k=3)

    @staticmethod
    def setup_stats(verbose):
        if not verbose:
            return None

        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)
        # stats.register("len", len)
        return stats

    def get_top_n(self):
        return self._top_n
