"""Phase 5 protocol: evaluation only; stdlib, deterministic canonical serialization."""
import hashlib
import json
from pathlib import Path

VERSION = '5.1.0'
MARKETS = ('BTTS', 'OVER_1_5', 'OVER_2_5', 'OVER_3_5', '1X2')
CLASSES = ('home', 'draw', 'away')
CONFIGS = tuple({'l2': x, 'learning_rate': 0.05, 'iterations': 400,
                 'tolerance': 1e-10} for x in (0.01, 0.1, 1.0))
POLICY = dict(version=VERSION, configs=CONFIGS, selection='validation_logloss',
              tie_break='logloss,brier,candidate_index', threshold=0.5,
              features='available catalog and accredited extractors; market-specific',
              preprocessing='train median; all-missing=0; population standard deviation; zero variance=1',
              optimizer='zero initialization; full batch gradient descent; unpenalized intercept',
              convergence='maximum absolute parameter step <= tolerance',
              calibration='descriptive_only', promotion=False,
              divergence_material_delta=0.01, oos_windows=3)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def immutable(path, value):
    path = Path(path)
    content = canonical(value) + '\n'
    if path.is_symlink() or (path.exists() and path.stat().st_nlink != 1):
        raise ValueError('unsafe_artifact')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text() != content:
            raise ValueError('immutable_artifact_conflict')
    else:
        with path.open('x') as f:
            f.write(content)


class TestSeal:
    """Do not expose TEST rows until a complete selection commitment is frozen."""
    def __init__(self, rows):
        self.__rows = tuple(rows)
        self.commitment = None
        self.opened = False

    def freeze(self, commitment):
        required = {'feature_names', 'preprocessing', 'family', 'candidates',
                    'selection_metric', 'tie_break', 'selected_config', 'model_hash'}
        if self.commitment is not None or not required <= commitment.keys():
            raise ValueError('invalid_test_commitment')
        self.commitment = canonical(commitment)

    def open(self):
        if self.commitment is None or self.opened:
            raise ValueError('test_sealed_or_already_opened')
        self.opened = True
        return self.__rows
