"""Expanding-window walk-forward splits with purging and an embargo."""

from __future__ import annotations

import dataclasses

import pandas as pd


@dataclasses.dataclass(frozen=True)
class Fold:
    """One walk-forward step.

    Attributes:
        number: Fold number, starting at 1.
        train_start: First training session.
        train_end: Last training session (after purge and embargo).
        test_start: First test session.
        test_end: Last test session.
    """

    number: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def walk_forward_folds(
    sessions: pd.DatetimeIndex,
    min_train: int,
    test_size: int,
    horizon: int,
    embargo: int,
) -> list[Fold]:
    """Split sessions into chronological train/test folds.

    Training always starts at the first session and ends before the test
    block. The last ``horizon`` sessions before the test block are purged
    because their labels look into the test period, and ``embargo``
    further sessions are dropped against serial correlation.

    Args:
        sessions: Sample sessions in ascending order.
        min_train: Minimum number of training sessions.
        test_size: Sessions per test block.
        horizon: Label horizon in sessions (purge length).
        embargo: Extra sessions dropped before each test block.

    Returns:
        The folds, in time order.
    """
    gap = horizon + embargo
    folds = []
    first_test = min_train + gap
    for number, start in enumerate(
        range(first_test, len(sessions), test_size), start=1
    ):
        end = min(start + test_size, len(sessions)) - 1
        folds.append(Fold(
            number=number,
            train_start=sessions[0],
            train_end=sessions[start - gap - 1],
            test_start=sessions[start],
            test_end=sessions[end],
        ))
    return folds
