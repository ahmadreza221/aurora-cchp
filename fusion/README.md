# GR180-CCHP in Autodesk Fusion

The design stays in the Python code (`cad/`, `sim/`): blade shapes come from the aero, stress and vibration calculations.
Fusion is for viewing, assembly, drawings and CAM. Change geometry in the code, re-export, and upload a new version in Fusion.

## E1 turbine stage
- `E1/*.step`: compact parts (one blade, one vane, revolved disc / rings, shaft), mm, X = engine axis.
  Regenerate: `freecadcmd fusion/export_e1_parts.py`.
- `GR180_E1_Import/`: Fusion script. Utilities > Scripts and Add-Ins > + > select the folder > Run.
  It builds the blisk (29 blades), the NGV ring (21 vanes) and the welded shaft. `KIND = 'cast'` gives the cast blanks.

## Claude driving Fusion directly (Fusion MCP server)
Fusion's MCP server (Preferences > General > API) listens on `http://127.0.0.1:27182/mcp`, on your Mac only. A cloud
session cannot reach it; a Claude Code session on the Mac can:

    cd <repo>
    claude mcp add --transport http fusion http://127.0.0.1:27182/mcp
    claude
