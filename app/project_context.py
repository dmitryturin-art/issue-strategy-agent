from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProjectProfile:
    key: str
    repo: str
    short_context: str


_PROJECTS: dict[str, ProjectProfile] = {
    "dmitryturin-art/pavodok_map": ProjectProfile(
        key="kimg",
        repo="dmitryturin-art/pavodok_map",
        short_context=(
            "Проект KIMG / pavodok_map: production Flutter web-first приложение "
            "для мониторинга гидропостов и раннего обнаружения паводков. "
            "Основной UX: карта с кластерами и цветами статуса -> карточка поста -> "
            "графики телеметрии -> фотоархив -> тревоги. "
            "Стек: Flutter, flutter_map, flutter_map_marker_cluster, charts, HTTP API. "
            "Проект legacy и монолитный, поэтому при формулировке задач и правок "
            "важны точечные, совместимые изменения без радикального переписывания."
        ),
    ),
}


def get_project_profile(repo: str) -> Optional[ProjectProfile]:
    return _PROJECTS.get(repo)

