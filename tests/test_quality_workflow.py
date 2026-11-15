"""Execute the real workflow's capture snippets in isolated disposable Git repos."""
import os
from pathlib import Path
import shlex
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


@pytest.mark.parametrize('changed', [False, True])
def test_same_job_base_and_candidate_capture_is_observable(tmp_path, changed):
    workflow = yaml.load((ROOT / '.github/workflows/sync.yml').read_text(), Loader=yaml.BaseLoader)
    steps = {s['name']: s for s in workflow['jobs']['sync']['steps']}
    base = steps['Record acquisition base']['run']
    stage = steps['Stage candidate']['run']
    stage_line = next(line for line in stage.splitlines() if line.startswith('git add '))
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'test')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    for name in shlex.split(stage_line)[2:]:
        target = tmp_path / name
        if name.endswith('/'):
            target = target / 'fixture'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('initial')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'fixture')
    output = tmp_path / 'capture-output'
    env = dict(os.environ, GITHUB_OUTPUT=str(output))
    captured = subprocess.check_output(['bash', '-e', '-c', base], cwd=tmp_path, env=env, text=True)
    assert 'acquisition_base_sha=' + git(tmp_path, 'rev-parse', 'HEAD') in captured
    assert 'acquisition_base_tree_sha=' + git(tmp_path, 'rev-parse', 'HEAD^{tree}') in captured
    if changed:
        (tmp_path / 'site/data.json').write_text('changed')
    captured = subprocess.check_output(['bash', '-e', '-c', stage], cwd=tmp_path, env=env, text=True)
    tree = git(tmp_path, 'write-tree')
    assert 'candidate_tree_sha=' + tree in captured
    assert 'candidate_changed=' + str(changed).lower() in captured
    assert 'tree_sha=' + tree in output.read_text()
    assert 'changed=' + str(changed).lower() in output.read_text()
