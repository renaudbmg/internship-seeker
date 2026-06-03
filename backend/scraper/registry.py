from .base import BaseScraper
from .sources.greenhouse import GreenhouseScraper
from .sources.jobteaser import JobTeaserScraper
from .sources.linkedin import LinkedInScraper
from .sources.smartrecruiters import SmartRecruitersScraper
from .sources.workday import WorkdayScraper
from .sources.wttj import WTTJScraper


def build_scrapers(settings) -> list[BaseScraper]:
    scrapers: list[BaseScraper] = []
    if settings.linkedin_enabled:
        scrapers.append(LinkedInScraper(settings))
    if settings.wttj_enabled:
        scrapers.append(WTTJScraper(settings))
    if settings.jobteaser_enabled:
        scrapers.append(JobTeaserScraper(settings))
    if settings.smartrecruiters_enabled:
        scrapers.append(SmartRecruitersScraper(settings))
    if settings.greenhouse_enabled:
        scrapers.append(GreenhouseScraper(settings))
    if settings.workday_enabled:
        scrapers.append(WorkdayScraper(settings))
    return scrapers
