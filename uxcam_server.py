#!/usr/bin/env python3
"""
UXCam MCP Server - Android SDK Integration
Compatible with latest MCP SDK
"""

import asyncio
import json
from pathlib import Path
import re
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult

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
    """Add UXCam Maven repository to settings.gradle"""
    target = SETTINGS_KTS if SETTINGS_KTS.exists() else SETTINGS_GROOVY
    if not target.exists():
        return "⚠️ settings.gradle file not found"

    txt = target.read_text()
    snippet = MAVEN_REPO_SNIPPET_KTS if target.suffix == ".kts" else MAVEN_REPO_SNIPPET
    
    if snippet in txt:
        return "ℹ️ Maven repo already present"
        
    new = re.sub(r"repositories\s*{",
                 lambda m: m.group(0) + f"\n        {snippet}",
                 txt, count=1)
    target.write_text(new)
    return f"✔️ Added UXCam Maven repo in {target}"

def add_dependency():
    """Add UXCam dependency to app/build.gradle"""
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
    """Find Application class files"""
    return (list(Path("app/src").rglob("*Application*.kt")) +
            list(Path("app/src").rglob("*Application*.java")))

def inject_init(app_key_expr):
    """Inject UXCam initialization code"""
    files = find_application_source()
    if not files:
        return "⚠️ No Application class found (wizard will fall back to Activity)"

    f = files[0]
    code = f.read_text()
    snippet = (KOTLIN_SNIPPET if f.suffix == ".kt" else JAVA_SNIPPET) % app_key_expr
    
    if "UXCam.startWithConfiguration" in code:
        return f"ℹ️ Init already present in {f.name}"

    # Add to onCreate() method
    code = re.sub(r'onCreate\s*\([^)]*\)\s*{',
                  lambda m: m.group(0) + "\n        " + snippet.strip().replace("\n", "\n        "),
                  code, count=1)
    f.write_text(code)
    return f"✔️ Inserted init code in {f.name}"

# ---------- MCP Server ----------
app = Server("uxcam-android-integration")

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="add_uxcam_android",
            description="Add UXCam SDK (v3.+) & init call to an Android project",
            inputSchema={
                "type": "object",
                "properties": {
                    "appKeyRef": {
                        "type": "string",
                        "description": "Reference used in code – e.g. BuildConfig.UXCAM_KEY or \"MY_KEY\""
                    }
                },
                "required": ["appKeyRef"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
    """Handle tool calls"""
    if name == "add_uxcam_android":
        app_key_ref = arguments.get("appKeyRef", "BuildConfig.UXCAM_KEY")
        
        reports = [
            add_repo(),
            add_dependency(),
            inject_init(app_key_ref)
        ]
        result = "; ".join([r for r in reports if r])
        
        return [TextContent(type="text", text=result)]
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    # Run the server using stdio transport
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())