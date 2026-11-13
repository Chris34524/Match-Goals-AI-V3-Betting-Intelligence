"""Read-only compatibility diagnostic; does not override any operational gate."""
from pathlib import Path
import subprocess

PRESENTATION_HELPER = '''def formato_lambda(valor, ancho):
    """Keep missing signals missing in JSON and printable in the diagnostic table."""
    return f"{'N/D':>{ancho}}" if valor is None else f"{valor:>{ancho}.3f}"


'''
OLD_TABLE = '''            f"{valores['local']:>17.3f}"
            f"{valores['visitante']:>17.3f}"
            f"{valores['total']:>12.3f}"'''
NEW_TABLE = '''            f"{formato_lambda(valores['local'], 17)}"
            f"{formato_lambda(valores['visitante'], 17)}"
            f"{formato_lambda(valores['total'], 12)}"'''


def presentation_only(current, baseline):
    if current == baseline:
        return True
    if current.count(PRESENTATION_HELPER) != 1 or current.count(NEW_TABLE) != 1:
        return False
    return current.replace(PRESENTATION_HELPER, '').replace(NEW_TABLE, OLD_TABLE) == baseline


def legacy_compatibility(root, ref='main'):
    """Exact authorized display patch only; every other protected change fails."""
    root = Path(root)
    changed = subprocess.check_output(['git', 'diff', ref, '--name-only', '--',
                                      'scraper/', 'analysis/', 'v3/ops/'], cwd=root, text=True).splitlines()
    if not changed:
        return True
    if changed != ['analysis/compare_lambda.py']:
        return False
    baseline = subprocess.check_output(['git', 'show', ref+':analysis/compare_lambda.py'], cwd=root, text=True)
    return presentation_only((root/'analysis/compare_lambda.py').read_text(encoding='utf-8'), baseline)
