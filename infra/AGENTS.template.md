# Infrastructure-specific instructions
Use `uv` for all Python inside Dockerfiles, CI and operator commands; Node tooling uses npm only.
Never bake keys or real banking data into images. Pin important image versions; review image upgrades explicitly.
Do not add public DB/ML ports, change network exposure or loosen environment checks to make a test pass.
Backups are not considered complete without an isolated restore drill.
