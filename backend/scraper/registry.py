from .base import BaseScraper
from .sources.france_travail import FranceTravailScraper
from .sources.greenhouse import GreenhouseScraper
from .sources.linkedin import LinkedInScraper
from .sources.smartrecruiters import SmartRecruitersScraper
from .sources.themuse import TheMuseScraper
from .sources.workday import WorkdayScraper


def build_scrapers(settings) -> list[BaseScraper]:
    scrapers: list[BaseScraper] = []
    if settings.linkedin_enabled:
        scrapers.append(LinkedInScraper(settings))
    if settings.themuse_enabled:
        scrapers.append(TheMuseScraper(settings))
    if settings.france_travail_enabled:
        scrapers.append(FranceTravailScraper(settings))
    if settings.smartrecruiters_enabled:
        scrapers.append(SmartRecruitersScraper(settings))
    if settings.greenhouse_enabled:
        scrapers.append(GreenhouseScraper(settings))
    if settings.workday_enabled:
        scrapers.append(WorkdayScraper(settings))
    return scrapers
