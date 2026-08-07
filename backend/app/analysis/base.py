from abc import ABC, abstractmethod

from app.core.analysis_context import AnalysisContext


class AnalysisModule(ABC):

    id: str
    title: str
    description: str


    @abstractmethod
    def supports(
        self,
        context: AnalysisContext,
    ) -> bool:
        """
        Can this module run on this dataset?
        """
        pass


    @abstractmethod
    def run(
        self,
        context: AnalysisContext,
    ) -> dict:
        """
        Execute the analysis and
        return an analysis dashboard.
        """
        pass