# uxcam_server.py  –  Android-only, compliant with UXCam rules (Updated for current MCP SDK)

from mcp.server import Server
from mcp.types import Tool
from pathlib import Path
import re
import asyncio

# ---------- constants ----------
GRADLE_GROOVY   = Path("app/build.gradle")
GRADLE_KTS      = Path("app/build.gradle.kts")
SETTINGS_GROOVY = Path("settings.gradle")
SETTINGS_KTS    = Path("settings.gradle.kts")

MAVEN_REPO_SNIPPET = 'maven { url "https://sdk.uxcam.com/android/" }'
MAVEN_REPO_SNIPPET_KTS = 'maven("https://sdk.uxcam.com/android/")'

DEP_LINE_GROOVY = "implementation 'com.uxcam:uxcam:3.+'"
DEP_LINE_KTS    = 'implementation("com.uxcam:uxcam:3.+")'

JAVA_SNIPPET = '''
import com.uxcam.UXCam;
import com.uxcam.datamodel.UXConfig;

String uxcamKey = %s;
UXConfig config = new UXConfig.Builder(uxcamKey)
        .enableIntegrationLogging(BuildConfig.DEBUG)
        .build();
UXCam.startWithConfiguration(config);
'''

KOTLIN_SNIPPET = '''
import com.uxcam.UXCam
import com.uxcam.datamodel.UXConfig

val uxcamKey = %s
val config = UXConfig.Builder(uxcamKey)
    .enableIntegrationLogging(BuildConfig.DEBUG)
    .build()
UXCam.startWithConfiguration(config)
'''

# ---------- helper functions ----------
def add_repo():
    target = SETTINGS_KTS if SETTINGS_KTS.exists() else SETTINGS_GROOVY
    if not target.exists():
        return "⚠️ settings.gradle file not found"

    txt = target.read_text()
    snippet = MAVEN_REPO_SNIPPET_KTS if target.suffix == ".kts" \
             else MAVEN_REPO_SNIPPET
    if snippet in txt:
        return "ℹ️ Maven repo already present"
    new = re.sub(r"repositories\s*{",
                 lambda m: m.group(0) + f"\n        {snippet}",
                 txt, count=1)
    target.write_text(new)
    return f"✔️ Added UXCam Maven repo in {target}"

def add_dependency():
    target = GRADLE_KTS if GRADLE_KTS.exists() else GRADLE_GROOVY
    if not target.exists():
        return "⚠️ app/build.gradle file not found"

    txt = target.read_text()
    line = DEP_LINE_KTS if target.suffix == ".kts" else DEP_LINE_GROOVY
    if line in txt:
        return "ℹ️ Dependency already present"
    new = re.sub(r"dependencies\s*{",
                 lambda m: m.group(0) + f"\n    {line}",
                 txt, count=1)
    target.write_text(new)
    return f"✔️ Added UXCam dependency in {target}"

def find_application_source():
    return (list(Path("app/src").rglob("*Application*.kt")) +
            list(Path("app/src").rglob("*Application*.java")))

def inject_init(app_key_expr):
    files = find_application_source()
    if not files:
        return "⚠️ No Application class found (wizard will fall back to Activity)"

    f = files[0]
    code = f.read_text()
    snippet = (KOTLIN_SNIPPET if f.suffix == ".kt" else JAVA_SNIPPET) % app_key_expr
    if "UXCam.startWithConfiguration" in code:
        return f"ℹ️ Init already present in {f.name}"

    # naive: drop into onCreate()
    code = re.sub(r'onCreate\s*\([^)]*\)\s*{',
                  lambda m: m.group(0) + "\n        " + snippet.strip().replace("\n", "\n        "),
                  code, count=1)
    f.write_text(code)
    return f"✔️ Inserted init code in {f.name}"

# ---------- MCP server setup ----------
server = Server("uxcam_android_integration")

@server.tool()
async def add_uxcam_android(appKeyRef: str) -> str:
    """
    Add UXCam SDK (v3.+) & init call to an Android project
    
    Args:
        appKeyRef: Reference used in code – e.g. BuildConfig.UXCAM_KEY or "MY_KEY"
    
    Returns:
        Summary of integration steps performed
    """
    reports = [
        add_repo(),
        add_dependency(),
        inject_init(appKeyRef)
    ]
    return "; ".join([r for r in reports if r])

async def main():
    # Import here to avoid issues with event loops
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())