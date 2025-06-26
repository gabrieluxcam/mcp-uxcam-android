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
MANIFEST_PATH   = Path("app/src/main/AndroidManifest.xml")

MAVEN_REPO_SNIPPET = 'maven { url "https://sdk.uxcam.com/android/" }'
MAVEN_REPO_SNIPPET_KTS = 'maven("https://sdk.uxcam.com/android/")'

DEP_LINE_GROOVY = "implementation 'com.uxcam:uxcam:3.+'"
DEP_LINE_KTS    = 'implementation("com.uxcam:uxcam:3.+")'

JAVA_SNIPPET = '''
        // UXCam initialization
        String uxcamKey = %s;
        UXConfig config = new UXConfig.Builder(uxcamKey)
                .enableIntegrationLogging(BuildConfig.DEBUG)
                .build();
        UXCam.startWithConfiguration(config);'''

KOTLIN_SNIPPET = '''
        // UXCam initialization
        val uxcamKey = %s
        val config = UXConfig.Builder(uxcamKey)
            .enableIntegrationLogging(BuildConfig.DEBUG)
            .build()
        UXCam.startWithConfiguration(config)'''

JAVA_IMPORTS = '''import com.uxcam.UXCam;
import com.uxcam.datamodel.UXConfig;'''

KOTLIN_IMPORTS = '''import com.uxcam.UXCam
import com.uxcam.datamodel.UXConfig'''

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

def find_application_class():
    """Find Application class files by scanning all Java/Kotlin files"""
    # Look through all source files, not just ones with "Application" in the name
    all_files = (list(Path("app/src").rglob("*.kt")) +
                 list(Path("app/src").rglob("*.java")))
    
    for file in all_files:
        try:
            content = file.read_text()
            # Check if this file contains a class that extends Application
            if ("extends Application" in content or 
                ": Application()" in content or 
                ": Application " in content):
                return file
        except Exception:
            # Skip files that can't be read
            continue
    
    return None

def find_launcher_activity():
    """Find the LAUNCHER activity from AndroidManifest.xml"""
    if not MANIFEST_PATH.exists():
        return None
    
    try:
        manifest_content = MANIFEST_PATH.read_text()
        
        # Find LAUNCHER activity
        launcher_pattern = r'<activity[^>]*android:name="([^"]*)"[^>]*>.*?<action[^>]*android:name="android\.intent\.action\.MAIN"[^>]*/>.*?<category[^>]*android:name="android\.intent\.category\.LAUNCHER"[^>]*/>.*?</activity>'
        match = re.search(launcher_pattern, manifest_content, re.DOTALL)
        
        if match:
            activity_name = match.group(1)
            # Convert to file path
            if activity_name.startswith('.'):
                # Relative to package
                activity_name = activity_name[1:]  # Remove leading dot
            
            # Try to find the activity file
            kt_files = list(Path("app/src").rglob(f"*{activity_name}*.kt"))
            java_files = list(Path("app/src").rglob(f"*{activity_name}*.java"))
            
            all_files = kt_files + java_files
            for file in all_files:
                content = file.read_text()
                if (activity_name.split('.')[-1] in content and 
                    ("extends Activity" in content or 
                     "extends AppCompatActivity" in content or
                     ": Activity" in content or
                     ": AppCompatActivity" in content)):
                    return file
    except Exception as e:
        print(f"Error parsing manifest: {e}")
    
    return None

def add_imports_to_file(file_path, is_kotlin):
    """Add UXCam imports to a file if not already present"""
    content = file_path.read_text()
    imports = KOTLIN_IMPORTS if is_kotlin else JAVA_IMPORTS
    
    # Check if imports already exist
    if "import com.uxcam.UXCam" in content:
        return content
    
    # Find where to insert imports (after package declaration)
    lines = content.split('\n')
    insert_index = 0
    
    for i, line in enumerate(lines):
        if line.strip().startswith('package '):
            insert_index = i + 1
            break
        elif line.strip().startswith('import ') and insert_index == 0:
            insert_index = i
            break
    
    # Insert imports
    import_lines = imports.split('\n')
    for j, import_line in enumerate(import_lines):
        lines.insert(insert_index + j, import_line)
    
    return '\n'.join(lines)

def inject_init_in_application(app_file, app_key_expr):
    """Inject UXCam initialization in Application.onCreate()"""
    is_kotlin = app_file.suffix == ".kt"
    content = app_file.read_text()
    
    # Check if already initialized
    if "UXCam.startWithConfiguration" in content:
        return f"ℹ️ UXCam already initialized in {app_file.name}"
    
    # Add imports
    content = add_imports_to_file(app_file, is_kotlin)
    
    # Add initialization code to onCreate()
    snippet = (KOTLIN_SNIPPET if is_kotlin else JAVA_SNIPPET) % app_key_expr
    
    # Look for onCreate method
    if is_kotlin:
        pattern = r'override\s+fun\s+onCreate\s*\(\s*\)\s*{'
    else:
        pattern = r'@Override\s*\n\s*public\s+void\s+onCreate\s*\(\s*\)\s*{'
    
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        # Find the super.onCreate() call and add after it
        start_pos = match.end()
        super_pattern = r'super\.onCreate\s*\(\s*\)\s*;?' if not is_kotlin else r'super\.onCreate\s*\(\s*\)'
        super_match = re.search(super_pattern, content[start_pos:])
        
        if super_match:
            insert_pos = start_pos + super_match.end()
            content = content[:insert_pos] + '\n' + snippet + content[insert_pos:]
        else:
            # No super call found, add right after opening brace
            content = content[:start_pos] + '\n' + snippet + content[start_pos:]
    else:
        return f"⚠️ Could not find onCreate() method in {app_file.name}"
    
    app_file.write_text(content)
    return f"✔️ Added UXCam initialization to {app_file.name}"

def inject_init_in_activity(activity_file, app_key_expr):
    """Inject UXCam initialization in Activity.onCreate()"""
    is_kotlin = activity_file.suffix == ".kt"
    content = activity_file.read_text()
    
    # Check if already initialized
    if "UXCam.startWithConfiguration" in content:
        return f"ℹ️ UXCam already initialized in {activity_file.name}"
    
    # Add imports
    content = add_imports_to_file(activity_file, is_kotlin)
    
    # Add initialization code to onCreate()
    snippet = (KOTLIN_SNIPPET if is_kotlin else JAVA_SNIPPET) % app_key_expr
    
    # Look for onCreate method
    if is_kotlin:
        pattern = r'override\s+fun\s+onCreate\s*\([^)]*\)\s*{'
    else:
        pattern = r'@Override\s*\n\s*protected\s+void\s+onCreate\s*\([^)]*\)\s*{'
    
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        # Find the super.onCreate() call and add after it
        start_pos = match.end()
        super_pattern = r'super\.onCreate\s*\([^)]*\)\s*;?' if not is_kotlin else r'super\.onCreate\s*\([^)]*\)'
        super_match = re.search(super_pattern, content[start_pos:])
        
        if super_match:
            insert_pos = start_pos + super_match.end()
            content = content[:insert_pos] + '\n' + snippet + content[insert_pos:]
        else:
            # No super call found, add right after opening brace
            content = content[:start_pos] + '\n' + snippet + content[start_pos:]
    else:
        return f"⚠️ Could not find onCreate() method in {activity_file.name}"
    
    activity_file.write_text(content)
    return f"✔️ Added UXCam initialization to {activity_file.name}"

def inject_init(app_key_expr):
    """Inject UXCam initialization code following the proper hierarchy"""
    
    # Step 1: Try to find Application class
    app_file = find_application_class()
    if app_file:
        return inject_init_in_application(app_file, app_key_expr)
    
    # Step 2: Fallback to LAUNCHER activity
    launcher_activity = find_launcher_activity()
    if launcher_activity:
        return inject_init_in_activity(launcher_activity, app_key_expr)
    
    # Step 3: No suitable location found
    return "⚠️ Could not find Application class or LAUNCHER activity to add UXCam initialization"

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