import typer

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Persistent 1688 draft automation."""


@app.command()
def version() -> None:
    """Print the uploader version."""
    typer.echo("1688-draft-automation 0.1.0")


if __name__ == "__main__":
    app()
