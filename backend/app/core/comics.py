"""Editorial formats and genres shared by every comic generation stage."""
COMIC_GENRES = {
    "manga": {
        "action": "Azione e avventura", "fantasy": "Fantasy", "romance": "Romance",
        "slice_of_life": "Slice of life", "mystery": "Mistero e thriller",
        "science_fiction": "Fantascienza", "horror": "Horror", "sports": "Sport",
    },
    "graphic_novel": {
        "literary": "Letterario", "memoir": "Autobiografico", "historical": "Storico",
        "noir": "Noir e thriller", "social": "Sociale e reportage",
        "fantasy": "Fantasy", "science_fiction": "Fantascienza", "adventure": "Avventura",
    },
}


def comic_direction(request):
    genre = COMIC_GENRES[request.comic_format][request.comic_genre]
    if request.comic_format == "graphic_novel":
        return (
            f"Formato: Graphic Novel. Sottogenere: {genre}. "
            "Romanzo a fumetti autoconclusivo, con sviluppo dei personaggi e regia autoriale. "
            "Composizione delle tavole e disegno coerenti con il sottogenere, senza imporre convenzioni manga. "
            "Lettura occidentale: vignette e balloon da sinistra a destra e dall'alto in basso. "
            "Bilancia scene, silenzi e didascalie; evita spiegazioni ridondanti."
        )
    return (
        f"Formato: Manga. Sottogenere: {genre}. Pubblico editoriale: {request.manga_type}. "
        "Linguaggio grafico manga: tratto espressivo, retini, ritmo dinamico e inquadrature cinematografiche. "
        "Edizione italiana con lettura da sinistra a destra e dall'alto in basso: "
        "ordina coerentemente vignette e balloon. Adatta temi e intensita al pubblico scelto."
    )
