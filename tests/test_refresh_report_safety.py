"""Publication reports are protected user files just like corpus and site output."""
import pytest
from tests.test_d2_integration import _refresh_fixture


@pytest.mark.parametrize('name',['source-health.json','publication-ledger.json'])
@pytest.mark.parametrize('late',[False,True])
def test_existing_untracked_reports_are_never_overwritten(tmp_path,monkeypatch,name,late):
    module,repo,prepared,expected,data=_refresh_fixture(tmp_path,monkeypatch)
    work=repo/'data'/name
    def write(*args,**kwargs):work.write_text('preserve user report\n')
    if late:monkeypatch.setattr(module,'build_all',write)
    else:write()
    with pytest.raises(ValueError):module.refresh({},repo,prepared,expected)
    assert work.read_text()=='preserve user report\n'
    assert (data/'entries/old.yaml').exists()
