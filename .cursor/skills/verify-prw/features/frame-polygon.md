# Name a millimetre frame

Name a millimetre frame prints a `fragment_local_mm` frame for a polygon. The command reads no image. The origin of the square below is the centroid of those four vertices.

## Sub-features

- `frame-square` prints the centroid origin and the millimetre axes for `0,0 2,0 2,2 0,2`.

## How to get to it (user POV)

- Run `prw frame --polygon X,Y X,Y X,Y X,Y` in a terminal.

## Driving it with verify-prw

Preconditions:

- Doctor prints `prw-verify doctor ok` for this run.
- `exports` has set `$RUN_ID`.

- **Name the square.** Run `uv run python .cursor/skills/verify-prw/verify_prw.py run --run "$RUN_ID" --feature frame-polygon --entry "prw frame square" --step square -- frame --polygon 0,0 2,0 2,2 0,2`. Exit code `0`. stderr is empty. `kind` is `fragment_local_mm`. `origin` is `[1.0,1.0]`. `axis_x_direction` is `+x right`. `axis_y_direction` is `+y down`. `unit` is `mm`. `origin_description` is `first-outline centroid`. Stdout does not contain `correct_join` or `hypothesis`.
- **Proof.** The evidence directory contains `square`.

## Gotchas

- The command takes no image path and no scale flag. `--claimed-ppi` is not a flag of `frame`.
- Vertices are `X,Y` tokens after one `--polygon` flag. A token without a comma exits `2`.
