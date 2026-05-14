from pathlib import Path


def sample_key_from_pdf(pdf_path: Path) -> str:
    return pdf_path.stem


def render_pdf_pages(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> list[Path]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to render PDF pages") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf_path)
    rendered_paths: list[Path] = []

    try:
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = output_dir / f"page-{page_index + 1:03d}.png"
            pixmap.save(output_path)
            rendered_paths.append(output_path)
    finally:
        document.close()

    return rendered_paths
