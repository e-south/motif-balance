"""
--------------------------------------------------------------------------------
motif-balance
tests/contract/test_prepared_scoring.py

Check exact scoring, bounded caches, and unchanged search decisions.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import itertools
import unittest

import numpy as np

from motif_balance import DesignSpec, MotifModel, MotifSpecification
from motif_balance.compile import compile_design
from motif_balance.errors import InvalidSequence
from motif_balance.scoring import _PreparedScorer as PreparedScorer
from motif_balance.scoring import evaluate


def problem(length=6, strands="both", background=(0.25,) * 4):
    models = [
        MotifModel(motif_id=name, probabilities=rows, background=background)
        for name, rows in [
            ("short", ((0.7, 0.1, 0.1, 0.1), (0.25, 0.25, 0.25, 0.25))),
            ("long", ((0.1, 0.6, 0.2, 0.1), (0.2, 0.1, 0.6, 0.1), (0.1, 0.1, 0.1, 0.7))),
            ("ties", ((0.4, 0.4, 0.1, 0.1), (0.1, 0.1, 0.4, 0.4))),
        ]
    ]
    return compile_design(
        DesignSpec(
            specifications=tuple(
                MotifSpecification(motif=m, direction="avoid" if i == 1 else "seek")
                for i, m in enumerate(models)
            ),
            length=length,
            count=1,
            evaluations=1,
            seed=7,
            strands=strands,
        )
    )


class ExactScoringTests(unittest.TestCase):
    def test_near_ties_follow_sequential_reference_rule(self):
        values = np.exp2(np.asarray((0.0, 0.4e-12, 0.8e-12, 1.2e-12)))
        values /= values.sum()
        model = MotifModel(
            motif_id="near_ties", probabilities=(tuple(values),), background=(0.25,) * 4
        )
        p = compile_design(
            DesignSpec(
                specifications=(MotifSpecification(motif=model, direction="seek"),),
                length=4,
                count=1,
                evaluations=1,
                seed=7,
                strands="forward",
            )
        )
        reference = evaluate("ACGT", p)
        self.assertEqual(reference.matches[0].start, 3)
        self.assertEqual(PreparedScorer(p)("ACGT"), reference)

    def test_window_cache_is_bounded_and_does_not_change_scores(self):
        p = problem()
        scorer = PreparedScorer(p, cache_bytes=512)
        for word in itertools.product("ACGT", repeat=3):
            sequence = "".join(word) * 2
            self.assertEqual(scorer(sequence), evaluate(sequence, p))
            self.assertLessEqual(scorer.cache_bytes_used, 512)
        scorer = PreparedScorer(p)
        first = scorer("ACGTAC")
        initial_work = scorer.window_evaluations
        self.assertEqual(scorer("ACGTAC"), first)
        self.assertEqual(scorer.window_evaluations, initial_work)
        self.assertGreater(scorer.cache_hits, 0)
        self.assertEqual(scorer.evaluation_cache_hits, 1)

    def test_exhaustive_short_words(self):
        for strands in ("forward", "both"):
            for background in ((0.25,) * 4, (0.1, 0.2, 0.3, 0.4)):
                p = problem(strands=strands, background=background)
                fast = PreparedScorer(p)
                for word in itertools.product("ACGT", repeat=6):
                    sequence = "".join(word)
                    self.assertEqual(fast(sequence), evaluate(sequence, p), sequence)

    def test_random_wide_models_and_short_windows(self):
        rng = np.random.default_rng(20261003)
        for width, length in ((1, 100), (7, 7), (7, 256), (30, 60), (100, 180)):
            probabilities = rng.dirichlet(np.ones(4), size=width)
            model = MotifModel(
                motif_id="random",
                probabilities=tuple(map(tuple, probabilities)),
                background=(0.25,) * 4,
            )
            p = compile_design(
                DesignSpec(
                    specifications=(MotifSpecification(motif=model, direction="seek"),),
                    length=length,
                    count=1,
                    evaluations=1,
                    seed=7,
                )
            )
            scorer = PreparedScorer(p)
            for _ in range(25):
                sequence = "".join(rng.choice(list("ACGT"), size=length))
                self.assertEqual(scorer(sequence), evaluate(sequence, p))

    def test_input_errors_and_lowercase(self):
        p = problem()
        fast = PreparedScorer(p)
        self.assertEqual(fast("acgtac"), evaluate("acgtac", p))
        for sequence in (None, "ACG", "ACGTNN", b"ACGTAC", "ÅCGTAC"):
            with self.assertRaises(InvalidSequence):
                fast(sequence)


if __name__ == "__main__":
    unittest.main()


def test_search_scoring_preserves_all_results_and_counts(monkeypatch, pairwise_spec):
    from motif_balance.search import engine, greedy, uniform

    for module, search in (
        (engine, engine.AnnealedSearchEngine()),
        (engine, engine.ExhaustiveSearchEngine()),
        (greedy, greedy.GreedySearchEngine()),
        (uniform, uniform.UniformRandomSearchEngine()),
    ):
        p = compile_design(pairwise_spec)
        calls = []

        def prepare(problem, calls=calls):
            scorer = PreparedScorer(problem)

            def score(sequence):
                calls.append(sequence)
                return scorer(sequence)

            return score

        with monkeypatch.context() as patch:
            patch.setattr(module, "_PreparedScorer", prepare, raising=False)
            actual = search.search(p)
        assert len(calls) == actual.evaluations_used
        with monkeypatch.context() as patch:
            patch.setattr(
                module, "_PreparedScorer", lambda problem: lambda seq: evaluate(seq, problem)
            )
            expected = search.search(p)
        assert actual == expected


def test_cache_can_be_disabled_and_is_scoped_to_one_request():
    p = problem()
    uncached = PreparedScorer(p, cache_bytes=0)
    first = uncached("ACGTAC")
    uncached("ACGTAC")
    assert uncached.cache_bytes_used == uncached.evaluation_cache_hits == 0
    assert first == evaluate("ACGTAC", p)
    other = problem(background=(0.1, 0.2, 0.3, 0.4))
    assert PreparedScorer(other)("ACGTAC") == evaluate("ACGTAC", other)
    for allowance in (-1, True, 1.5):
        with unittest.TestCase().assertRaises(ValueError):
            PreparedScorer(p, cache_bytes=allowance)


def test_cache_eviction_preserves_scores_and_entry_allowance():
    p = problem()
    scorer = PreparedScorer(p, cache_bytes=16_000)
    first = "AAAAAA"
    for bases in itertools.product("ACGT", repeat=3):
        sequence = "AAA" + "".join(bases)
        assert scorer(sequence) == evaluate(sequence, p)
        assert scorer.cache_bytes_used <= 16_000

    # Both caches filled and evicted entries, rather than simply refusing them.
    assert 0 < len(scorer.cache) < scorer.window_evaluations
    assert len(scorer.evaluation_cache) == 1
    assert first not in scorer.evaluation_cache
    previous_hits = scorer.evaluation_cache_hits
    assert scorer(first) == evaluate(first, p)
    assert scorer.evaluation_cache_hits == previous_hits
    assert scorer.cache_bytes_used <= 16_000


def test_evaluation_accounting_covers_allocated_model_fields(pairwise_spec):
    import sys

    scorer = PreparedScorer(compile_design(pairwise_spec))
    result = scorer("ACGT")

    # Include validated model containers and values, excluding shared class data.
    def model_size(model):
        return (
            sys.getsizeof(model)
            + sys.getsizeof(model.__dict__)
            + sys.getsizeof(model.__pydantic_fields_set__)
            + sum(sys.getsizeof(value) for value in model.__dict__.values())
        )

    measured = model_size(result) + sum(model_size(m) for m in result.matches)
    assert scorer.evaluation_size >= measured + 160  # cache mapping entry
