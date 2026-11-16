from html import escape
from typing import Any, Dict

PROJECT_ART = {
    "compost-mini": ("#607a50", '<path d="M92 88h136l-13 104H105z" fill="#b8794f"/><path d="M84 82h152v15H84z" fill="#8b583a"/><path d="M115 73c-14-18 2-31 16-39-2 17 10 20 9 35m17 3c-4-21 12-29 28-35-8 17-2 24-5 35" fill="none" stroke="#607a50" stroke-width="9" stroke-linecap="round"/><path d="M107 121h105m-101 25h99m-95 25h91" stroke="#d7a47b" stroke-width="6" stroke-linecap="round"/>'),
    "mulch-garden": ("#728452", '<path d="M65 177c34-25 64-20 95 0 30-22 61-20 95 0v34H65z" fill="#806349"/><path d="M74 174c19-20 40-24 64-4m16 2c20-25 42-26 69-2" fill="none" stroke="#728452" stroke-width="12" stroke-linecap="round"/><path d="M111 167c-3-23 8-42 26-53m47 52c0-23-9-39-25-51" fill="none" stroke="#536843" stroke-width="7" stroke-linecap="round"/><path d="M137 128c-22-20-35-12-36 4 15 13 27 9 36-4zm22-12c18-21 32-17 36-2-12 15-24 14-36 2z" fill="#8d9b65"/>'),
    "organic-soil-enrichment": ("#758554", '<path d="M105 124h110l-12 79h-86z" fill="#b8794f"/><path d="M97 118h126v14H97z" fill="#8b583a"/><path d="M160 120V68m0 22-27-23m27 35 27-26" fill="none" stroke="#536843" stroke-width="8" stroke-linecap="round"/><path d="M133 69c-2-17-18-20-30-13 5 15 15 20 30 13zm53 0c2-17 18-20 30-13-5 15-15 20-30 13z" fill="#879663"/><path d="M122 152h76m-71 22h66" stroke="#d9a77d" stroke-width="5"/>'),
    "organizer-cardboard": ("#b47a53", '<path d="M70 111h180v99H70z" fill="#c69469"/><path d="M70 105h180v14H70z" fill="#9b6849"/><path d="M126 111v99m64-99v99" stroke="#8b6045" stroke-width="8"/><path d="M93 105V76h24v29m49 0V68h24v37m49 0V79h21v26" fill="#8d7058"/><path d="M88 139h25m-25 16h25m38-16h25m-25 16h25m40-16h25m-25 16h25" stroke="#ead7bd" stroke-width="5" stroke-linecap="round"/>'),
    "gift-box-cardboard": ("#b47a53", '<path d="M91 119h139v91H91z" fill="#b9825a"/><path d="M80 105h161v21H80z" fill="#d2a877"/><path d="M155 105V67m0 23c-43-42-65 3 0 15m0-15c44-42 66 3 0 15" fill="none" stroke="#8b583a" stroke-width="9" stroke-linecap="round"/><path d="M151 127v78" stroke="#e1c399" stroke-width="7"/>'),
    "cardboard-mini-shelf": ("#b47a53", '<path d="M85 69h150v142H85z" fill="#b9825a"/><path d="M74 75h172v13H74zm0 58h172v13H74zm0 58h172v13H74z" fill="#8b6045"/><path d="M98 97h45v25H98zm75 0h44v25h-44zm-75 58h45v25H98zm75 0h44v25h-44z" fill="#d8b28a"/>'),
    "glass-vase": ("#4f8b87", '<path d="M137 67h46v33l-10 18v75c0 18-56 18-56 0v-75l-10-18V67h30" fill="#c2ded3" fill-opacity=".72" stroke="#4f8b87" stroke-width="7"/><path d="M125 131h50m-49 27h48" stroke="#8db8aa" stroke-width="6"/><path d="M159 116V78m0 22-23-17m23 24 24-18" fill="none" stroke="#718657" stroke-width="5" stroke-linecap="round"/><path d="M136 83c-10-12-20-7-21 2 9 8 16 7 21-2zm45-2c10-11 20-7 21 2-9 8-16 7-21-2z" fill="#90a36c"/>'),
    "glass-flower-vase": ("#4f8b87", '<path d="M128 94h64l-7 95c-2 18-48 18-50 0z" fill="#c2ded3" fill-opacity=".72" stroke="#4f8b87" stroke-width="7"/><path d="M160 105V57m0 34-28-25m28 37 25-32" fill="none" stroke="#718657" stroke-width="5" stroke-linecap="round"/><path d="M132 65c-15-16-30-9-28 3 12 11 22 9 28-3zm51-1c14-18 29-12 29 1-12 12-22 11-29-1zm-13-7c-5-21 10-28 20-21 0 15-7 22-20 21z" fill="#d58a70"/><path d="M135 139h51" stroke="#8db8aa" stroke-width="6"/>'),
    "glass-storage-jar": ("#4f8b87", '<path d="M114 94h92v105c0 14-92 14-92 0z" fill="#c2ded3" fill-opacity=".68" stroke="#4f8b87" stroke-width="7"/><path d="M107 80h106v19H107z" fill="#668b7b"/><path d="M121 133h78" stroke="#8db8aa" stroke-width="6"/><path d="M135 164h49" stroke="#8db8aa" stroke-width="6"/><path d="M135 69h49" stroke="#d6e5d7" stroke-width="7" stroke-linecap="round"/>'),
    "glass-terrarium": ("#4f8b87", '<path d="M105 83h110v108c0 23-110 23-110 0z" fill="#c2ded3" fill-opacity=".5" stroke="#4f8b87" stroke-width="7"/><path d="M105 143h110" stroke="#8b7158" stroke-width="8"/><path d="M160 142v-39m0 27-20-19m20 31 22-24" fill="none" stroke="#607a50" stroke-width="6" stroke-linecap="round"/><path d="M140 112c-13-15-24-9-23 2 10 8 18 7 23-2zm42-2c12-15 24-10 23 1-10 9-18 8-23-1z" fill="#8c9e69"/><circle cx="128" cy="170" r="6" fill="#b8794f"/><circle cx="190" cy="174" r="5" fill="#d2a877"/>'),
    "metal-planter": ("#777d78", '<path d="M105 107h110l-11 91h-88z" fill="#aeb6ae"/><path d="M96 99h128v16H96z" fill="#777d78"/><path d="M160 100V58m0 28-26-21m26 32 27-24" fill="none" stroke="#607a50" stroke-width="7" stroke-linecap="round"/><path d="M134 67c-17-18-31-9-28 3 12 11 22 9 28-3zm54-1c15-17 30-9 27 3-12 11-21 9-27-3z" fill="#8c9e69"/><path d="M116 139h87m-83 25h78" stroke="#d0d5cf" stroke-width="5"/>'),
    "metal-desk-organizer": ("#777d78", '<path d="M98 92h50v111H98z" fill="#9ea7a1"/><path d="M156 112h42v91h-42z" fill="#b4bcb6"/><path d="M202 81h27v122h-27z" fill="#858e89"/><path d="M108 92V53m16 39V66m45 46V69m14 43V58m27 23V48" stroke="#6b5543" stroke-width="6" stroke-linecap="round"/><path d="M91 202h143" stroke="#777d78" stroke-width="8" stroke-linecap="round"/>'),
    "metal-herb-holder": ("#777d78", '<path d="M118 106h84l-8 92h-68z" fill="#aeb6ae"/><path d="M111 99h98v14h-98z" fill="#777d78"/><path d="M160 98V61m0 25-24-21m24 33 25-22" fill="none" stroke="#607a50" stroke-width="6" stroke-linecap="round"/><path d="M137 67c-15-16-28-8-25 3 11 10 19 8 25-3zm48 0c14-16 27-8 24 3-11 10-19 8-24-3z" fill="#8c9e69"/><path d="M126 139h68" stroke="#d0d5cf" stroke-width="5"/>'),
    "paper-notebook": ("#788e79", '<path d="M104 69h115v143H104z" fill="#d6c6a9"/><path d="M113 69h106v143H113z" fill="#eee5d3"/><path d="M111 69v143" stroke="#788e79" stroke-width="8"/><path d="M126 104h72m-72 18h72m-72 18h72m-72 18h57m-57 18h66" stroke="#a4b09b" stroke-width="4"/><path d="M98 83h13m-13 20h13m-13 20h13m-13 20h13m-13 20h13m-13 20h13" stroke="#788e79" stroke-width="3"/>'),
    "paper-card": ("#788e79", '<path d="M87 83h146v110H87z" fill="#e9ddc8"/><path d="M160 83v110" stroke="#bcae93" stroke-width="3"/><path d="M119 154c15-17 27-17 41 0m-39-10c14-25 25-27 39-2" fill="none" stroke="#788e79" stroke-width="5"/><path d="M135 112c-12-13-24-5-19 6 8 7 15 4 19-6zm39 4c10-15 21-8 18 3-8 7-14 5-18-3z" fill="#c77d65"/><path d="M178 131h35m-35 10h26" stroke="#bcae93" stroke-width="4"/>'),
    "paper-folded-bag": ("#788e79", '<path d="M109 100h102l-8 105h-86z" fill="#d9ccb4"/><path d="M133 103V76c0-34 54-34 54 0v27" fill="none" stroke="#788e79" stroke-width="7"/><path d="M121 133h79m-77 20h76m-74 20h72" stroke="#b4a58c" stroke-width="4"/><path d="M140 119h38" stroke="#8a9b83" stroke-width="5"/>'),
    "paper-folded-decoration": ("#788e79", '<path d="M72 100c26-20 48 20 73 0s48 20 73 0" fill="none" stroke="#a88966" stroke-width="4"/><path d="M94 103v30m48-30v30m49-30v30" stroke="#a88966" stroke-width="3"/><path d="M94 132l-14 25 14-5 14 5zm48 0-14 25 14-5 14 5zm49 0-14 25 14-5 14 5z" fill="#d4b989"/><path d="M94 133l14 24m34-24-14 24m49-24-14 24" stroke="#ede2cd" stroke-width="3"/>'),
    "plastic-planter": ("#bd8050", '<path d="M111 104h98l-10 95h-78z" fill="#c7d7c5"/><path d="M102 97h116v15H102z" fill="#bd8050"/><path d="M160 98V57m0 26-26-21m26 32 25-23" fill="none" stroke="#607a50" stroke-width="7" stroke-linecap="round"/><path d="M134 64c-16-17-30-8-27 4 12 10 21 8 27-4zm52 0c15-17 29-8 26 4-12 10-21 8-26-4z" fill="#8c9e69"/><path d="M120 144h81" stroke="#9bb6a0" stroke-width="5"/>'),
    "plastic-organizer": ("#bd8050", '<path d="M78 104h164v99H78z" fill="#c7d7c5"/><path d="M71 96h178v16H71z" fill="#bd8050"/><path d="M132 106v97m53-97v97" stroke="#91ad98" stroke-width="6"/><path d="M99 97V60m17 37V72m48 34V53m15 50V68m49 27V61" stroke="#79654e" stroke-width="6" stroke-linecap="round"/><path d="M92 135h26m-26 17h26m31-17h22m-22 17h22m27-17h30m-30 17h30" stroke="#f0eadc" stroke-width="4"/>'),
    "plastic-sprayer": ("#bd8050", '<path d="M125 104h78l-8 99h-62z" fill="#c7d7c5"/><path d="M142 97V75h40v19h26v13h-30V97z" fill="#bd8050"/><path d="M151 76V60h52v10h-23" fill="none" stroke="#bd8050" stroke-width="8" stroke-linejoin="round"/><path d="M204 65h21m-5-8 9 8-9 8" fill="none" stroke="#799184" stroke-width="4"/><path d="M137 143h56m-54 21h53" stroke="#91ad98" stroke-width="5"/>'),
    "plastic-seed-starter": ("#bd8050", '<path d="M74 123h172l-13 78H87z" fill="#c7d7c5"/><path d="M68 116h184v14H68z" fill="#bd8050"/><path d="M116 123v66m58-66v66m-87-33h146" stroke="#91ad98" stroke-width="5"/><path d="M106 116V86m58 30V78m58 38V86" stroke="#607a50" stroke-width="5"/><path d="M106 91c-14-14-26-7-23 3 10 8 17 7 23-3zm0 0c14-14 26-7 23 3-10 8-17 7-23-3zm58-8c-14-14-26-7-23 3 10 8 17 7 23-3zm0 0c14-14 26-7 23 3-10 8-17 7-23-3z" fill="#8c9e69"/>'),
    "plastic-cable-holder": ("#bd8050", '<path d="M88 113h144v91H88z" fill="#c7d7c5"/><path d="M79 101h162v20H79z" fill="#bd8050"/><path d="M158 101v19" stroke="#965f39" stroke-width="5"/><path d="M112 150c0-18 28-18 28 0v20c0 18 30 18 30 0v-20c0-18 29-18 29 0" fill="none" stroke="#758778" stroke-width="7" stroke-linecap="round"/><path d="M103 184h111" stroke="#91ad98" stroke-width="5"/>'),
}

MATERIAL_LABELS = {
    "BIODEGRADABLE": "VẬT LIỆU HỮU CƠ",
    "CARDBOARD": "BÌA CARTON TÁI SỬ DỤNG",
    "GLASS": "THỦY TINH TÁI SỬ DỤNG",
    "METAL": "KIM LOẠI TÁI SỬ DỤNG",
    "PAPER": "GIẤY TÁI SỬ DỤNG",
    "PLASTIC": "NHỰA TÁI SỬ DỤNG",
}


def render_project_art(project: Dict[str, Any]) -> str:
    project_id = str(project.get("id") or "")
    art = PROJECT_ART.get(project_id)
    if not art:
        raise ValueError(f"No project illustration is defined for {project_id!r}")

    color, illustration = art
    title = escape(str(project.get("title") or project.get("name") or "Dự án tái sử dụng"))
    material = escape(MATERIAL_LABELS.get(str(project.get("material") or ""), "TÁI SỬ DỤNG"))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720" role="img" aria-labelledby="title description">
<title id="title">{title} — minh họa thành phẩm</title>
<desc id="description">Minh họa riêng cho dự án {title}, làm từ {material.lower()}.</desc>
<rect width="960" height="720" fill="#e9e5d9"/>
<circle cx="765" cy="155" r="208" fill="{color}" opacity=".10"/>
<circle cx="120" cy="612" r="196" fill="#bd8050" opacity=".08"/>
<path d="M0 520c180-65 310 40 488-5s300-56 472 10v195H0z" fill="#f3f0e7"/>
<g transform="translate(320 105) scale(1.35)" stroke-linejoin="round">{illustration}</g>
<path d="M140 568h680" stroke="#c8c2b4" stroke-width="2"/>
<text x="140" y="615" fill="#193b2e" font-family="Georgia,serif" font-size="35">{title}</text>
<text x="142" y="651" fill="{color}" font-family="Arial,sans-serif" font-size="15" font-weight="700" letter-spacing="2">{material}</text>
<text x="820" y="651" text-anchor="end" fill="#77796e" font-family="Arial,sans-serif" font-size="12" letter-spacing="1">MINH HỌA THÀNH PHẨM</text>
</svg>"""
