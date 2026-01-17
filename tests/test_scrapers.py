"""Základní testy pro scrapery."""

import pytest


def test_imports():
    """Test že základní importy fungují."""
    from scrapers.grants.sources import models
    from scrapers.grants.sources import base
    from scrapers.grants.sources import registry

    assert models is not None
    assert base is not None
    assert registry is not None


def test_grant_model():
    """Test vytvoření GrantContent modelu."""
    from scrapers.grants.sources.models import GrantContent

    grant = GrantContent(
        source_url="https://example.cz/grant/1",
        scraper_name="TestScraper",
    )

    assert grant.source_url == "https://example.cz/grant/1"
    assert grant.scraper_name == "TestScraper"


def test_new_scrapers():
    """Test instantiation of new scrapers."""
    from scrapers.grants.sources.mfcr_cz import MFCRCzScraper
    from scrapers.grants.sources.eeagrants_cz import EEAGrantsCzScraper
    from scrapers.grants.sources.mkcr_cz import MKCRCzScraper
    from scrapers.grants.sources.army_cz import ArmyCzScraper
    from scrapers.grants.sources.mpo_cz import MPOCzScraper

    assert MFCRCzScraper() is not None
    assert EEAGrantsCzScraper() is not None
    assert MKCRCzScraper() is not None
    assert ArmyCzScraper() is not None
    assert MPOCzScraper() is not None


def test_can_handle():
    """Test can_handle method of new scrapers."""
    from scrapers.grants.sources.mfcr_cz import MFCRCzScraper
    from scrapers.grants.sources.eeagrants_cz import EEAGrantsCzScraper
    from scrapers.grants.sources.mpo_cz import MPOCzScraper

    assert MFCRCzScraper().can_handle("https://www.mfcr.cz/cs/...") is True
    assert EEAGrantsCzScraper().can_handle("https://www.eeagrants.cz/cs/...") is True
    assert MPOCzScraper().can_handle("https://www.mpo.cz/cz/...") is True
    assert MPOCzScraper().can_handle("https://optak.gov.cz/...") is False


def test_new_agency_scrapers():
    """Test instantiation and can_handle of agency scrapers (MZe, MD, NSA)."""
    from scrapers.grants.sources.mze_cz import MZeCzScraper
    from scrapers.grants.sources.mdcr_cz import MDCrScraper
    from scrapers.grants.sources.nsa_gov_cz import NSAGovCzScraper

    s_mze = MZeCzScraper()
    s_md = MDCrScraper()
    s_nsa = NSAGovCzScraper()

    assert s_mze.can_handle("https://eagri.cz/public/web/mze/dotace/") is True
    assert s_mze.can_handle("https://www.szif.cz/cs/vyzvy") is True
    assert s_md.can_handle("https://www.mdcr.cz/Dokumenty/Strategie") is True

def test_opjak_scraper():
    from scrapers.grants.sources.opjak_cz import OPJAKCzScraper
    scraper = OPJAKCzScraper()
    assert scraper.can_handle("https://opjak.cz/vyzvy/vyzva-c-02_24_036-teaming-cz-iii/")
    assert not scraper.can_handle("https://example.com")


def test_tacr_scraper():
    from scrapers.grants.sources.tacr_cz import TACRCzScraper
    scraper = TACRCzScraper()
    assert scraper.can_handle("https://tacr.gov.cz/program/program-prostredi-pro-zivot-2/")
    assert scraper.can_handle("https://www.tacr.cz/soutez/program-prostredi-pro-zivot-2/")
    assert not scraper.can_handle("https://example.com")


def test_gacr_scraper():
    from scrapers.grants.sources.gacr_cz import GACRCzScraper
    scraper = GACRCzScraper()
    assert scraper.can_handle("https://gacr.cz/zadavaci-dokumentace/")
    assert not scraper.can_handle("https://example.com")


def test_msmt_scraper():
    from scrapers.grants.sources.msmt_cz import MSMTCzScraper
    scraper = MSMTCzScraper()
    assert scraper.can_handle("https://www.msmt.cz/vzdelavani/dotacni-vyzvy-k-pedagogickym-pracovnikum")
    assert not scraper.can_handle("https://opjak.cz/vyzvy/")
    assert not scraper.can_handle("https://example.com")


def test_mzcr_scraper():
    from scrapers.grants.sources.mzcr_cz import MZCrCzScraper
    scraper = MZCrCzScraper()
    assert scraper.can_handle("https://www.mzcr.cz/category/uředni-deska/granty-a-dotace/")
    assert not scraper.can_handle("https://example.com")


def test_justice_scraper():
    from scrapers.grants.sources.justice_cz import JusticeCzScraper
    scraper = JusticeCzScraper()
    assert scraper.can_handle("https://www.justice.cz/web/msp/dotace")
    assert not scraper.can_handle("https://example.com")


def test_mzv_scraper():
    from scrapers.grants.sources.mzv_cz import MZVCzScraper
    scraper = MZVCzScraper()
    assert scraper.can_handle("https://www.mzv.cz/jnp/cz/o_ministerstvu/dotace/index.html")
    assert not scraper.can_handle("https://example.com")


def test_vlada_scraper():
    from scrapers.grants.sources.vlada_cz import VladaCzScraper
    scraper = VladaCzScraper()
    assert scraper.can_handle("https://www.vlada.cz/cz/pprv/dotace/dotace-771/")
    assert not scraper.can_handle("https://example.com")
