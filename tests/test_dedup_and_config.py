"""Dédup (job_id) et parsing de la config (clés Gemini, listes de titres)."""

from backend.config import Settings
from backend.scraper.base import RawJob
from backend.scraper.sources.linkedin import linkedin_job_id_from_url


def test_job_id_stable_par_source_id():
    a = RawJob(title="X", company="Y", source="linkedin", url="u1", source_id="123")
    b = RawJob(title="AUTRE", company="ZZZ", source="linkedin", url="u2", source_id="123")
    # même source_id → même id (dédup), peu importe titre/url
    assert a.job_id() == b.job_id()


def test_job_id_diffre_sans_source_id():
    a = RawJob(title="Data", company="Acme", source="wttj", url="u")
    b = RawJob(title="Autre", company="Acme", source="wttj", url="u")
    assert a.job_id() != b.job_id()


def test_linkedin_job_id_extraction():
    assert linkedin_job_id_from_url("https://fr.linkedin.com/jobs/view/x-4412806676") == "4412806676"
    assert linkedin_job_id_from_url("https://www.linkedin.com/jobs/view/3621584441") == "3621584441"
    assert linkedin_job_id_from_url("") is None
    assert linkedin_job_id_from_url(None) is None


def test_gemini_key_list_dedup_et_ordre():
    s = Settings(gemini_api_key="A", gemini_api_keys="B, C, A")
    # principale d'abord, dédupliquée, sans doublon de A
    assert s.gemini_key_list == ["A", "B", "C"]


def test_gemini_key_list_vide():
    s = Settings(gemini_api_key=None, gemini_api_keys=None)
    assert s.gemini_key_list == []


def test_title_lists_parsing():
    s = Settings(title_block="vendeur, coach , ")
    assert s.title_block_list == ["vendeur", "coach"]
