from typing import Any, Dict, List, Optional

from services.recycling_service import (
    get_material_projects,
    get_recycling_profile,
    list_materials,
    normalize_material,
)

def list_projects(
    material: Optional[str] = None,
    difficulty: Optional[str] = None,
    max_minutes: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    materials = [normalize_material(material)] if material else list_materials()
    projects = []
    for material_name in materials:
        profile = get_recycling_profile(material_name)
        for project in get_material_projects(material_name, difficulty, max_minutes):
            if category and str(project.get("category", "")).casefold() != category.casefold():
                continue
            title = project.get("title") or project.get("name", "Dự án tái sử dụng")
            final_product = str(project.get("final_product") or title).rstrip(".")
            projects.append({
                **project,
                "title": title,
                "description": project.get("description") or f"Tận dụng {profile.get('display_name', material_name).lower()} để tạo {final_product.lower()}.",
                "image": f"/project-art/{project.get('id')}.svg",
                "safety": project.get("safety") or project.get("warning", ""),
                "material": material_name,
                "display_name": profile.get("display_name", material_name.title()),
            })
    return projects


def get_project_by_id(project_id: str) -> Dict[str, Any]:
    target = (project_id or "").strip()
    for project in list_projects():
        if project.get("id") == target:
            return project
    return {}