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

# ---------- repository functions ----------
def add_repo():
    """Add UXCam Maven repository to settings.gradle in dependencyResolutionManagement"""
    # Priority 1: Try settings.gradle first
    target = SETTINGS_KTS if SETTINGS_KTS.exists() else SETTINGS_GROOVY
    
    if target.exists():
        txt = target.read_text()
        snippet = MAVEN_REPO_SNIPPET_KTS if target.suffix == ".kts" else MAVEN_REPO_SNIPPET
        
        if snippet in txt:
            return "ℹ️ Maven repo already present in settings.gradle"
        
        # Look for dependencyResolutionManagement { repositories { pattern
        pattern = r'dependencyResolutionManagement\s*{[^}]*repositories\s*{'
        match = re.search(pattern, txt, re.DOTALL)
        
        if match:
            # Add to dependencyResolutionManagement repositories
            new = re.sub(r'(dependencyResolutionManagement\s*{[^}]*repositories\s*{)',
                        lambda m: m.group(0) + f"\n        {snippet}",
                        txt, count=1)
            target.write_text(new)
            return f"✔️ Added UXCam Maven repo in {target} (dependencyResolutionManagement)"
        else:
            # No dependencyResolutionManagement found, fall back to app/build.gradle
            return add_repo_fallback()
    else:
        # No settings.gradle found, fall back to app/build.gradle
        return add_repo_fallback()

def add_repo_fallback():
    """Fallback: Add UXCam Maven repository to app/build.gradle"""
    target = GRADLE_KTS if GRADLE_KTS.exists() else GRADLE_GROOVY
    if not target.exists():
        return "⚠️ Neither settings.gradle nor app/build.gradle found"

    txt = target.read_text()
    snippet = MAVEN_REPO_SNIPPET_KTS if target.suffix == ".kts" else MAVEN_REPO_SNIPPET
    
    if snippet in txt:
        return "ℹ️ Maven repo already present in app/build.gradle"
        
    # Look for repositories block in app/build.gradle
    new = re.sub(r"repositories\s*{",
                 lambda m: m.group(0) + f"\n        {snippet}",
                 txt, count=1)
    target.write_text(new)
    return f"✔️ Added UXCam Maven repo in {target} (fallback)"

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

# ---------- app key handling functions ----------
def handle_app_key(app_key_ref):
    """
    Intelligently handle app key reference with proper security and BuildConfig setup
    
    Scenarios:
    1. No key provided -> Guide user to secure setup
    2. Direct string key -> Store in local.properties + expose via BuildConfig
    3. Variable name -> Check BuildConfig first, then local.properties + expose via BuildConfig
    4. BuildConfig.X -> Validate it exists or help create it
    """
    
    if not app_key_ref or app_key_ref.strip() == "":
        return handle_no_key_provided()
    
    # Remove quotes if user provided them
    cleaned_key = app_key_ref.strip().strip('"').strip("'")
    
    # Scenario 1: Already a BuildConfig reference
    if cleaned_key.startswith("BuildConfig."):
        var_name = cleaned_key.replace("BuildConfig.", "")
        return handle_buildconfig_reference(var_name)
    
    # Scenario 2: Direct API key (long string, contains dashes/alphanumeric)
    if is_likely_api_key(cleaned_key):
        return handle_direct_api_key(cleaned_key)
    
    # Scenario 3: Variable name (user wants to reference a variable)
    return handle_variable_reference(cleaned_key)

def is_likely_api_key(value):
    """Check if value looks like an actual API key"""
    # UXCam keys are typically long alphanumeric strings
    return (len(value) > 20 and 
            any(c.isalnum() for c in value) and
            not value.isalpha() and  # Not just letters
            not value.isdigit())     # Not just numbers

def handle_no_key_provided():
    """Guide user when no key is provided"""
    return """⚠️ UXCam app key required. Please specify your key:
1. Get your key from UXCam dashboard
2. Add to local.properties: UXCAM_KEY=your-actual-key
3. Run: "Add UXCam with app key UXCAM_KEY" """

def handle_buildconfig_reference(var_name):
    """Handle BuildConfig.VARIABLE_NAME references"""
    # First check if BuildConfig variable is already properly exposed
    if is_buildconfig_variable_exposed(var_name):
        # It's already exposed in BuildConfig - we're good to go!
        return f'BuildConfig.{var_name}'
    
    # Not exposed yet - try to find it in local.properties and expose it
    local_props_value = find_in_local_properties(var_name)
    if local_props_value:
        expose_in_buildconfig(var_name)
        return f'BuildConfig.{var_name}'
    else:
        return f"""⚠️ BuildConfig.{var_name} not found. Please either:
1. Add to local.properties: {var_name}=your-actual-key, OR
2. Ensure it's already exposed in build.gradle buildConfigField
Then run this command again"""

def handle_direct_api_key(api_key):
    """Securely handle direct API key - store in local.properties"""
    # Never hardcode - store securely
    store_in_local_properties("UXCAM_KEY", api_key)
    expose_in_buildconfig("UXCAM_KEY")
    
    return 'BuildConfig.UXCAM_KEY'

def handle_variable_reference(var_name):
    """Handle variable name reference"""
    # First check if it's already exposed in BuildConfig
    if is_buildconfig_variable_exposed(var_name):
        return f'BuildConfig.{var_name}'
    
    # Not in BuildConfig yet - look for it in local.properties
    value = find_in_local_properties(var_name)
    
    if value:
        # Found it, expose in BuildConfig
        expose_in_buildconfig(var_name)
        return f'BuildConfig.{var_name}'
    else:
        return f"""⚠️ Variable '{var_name}' not found. Please either:
1. Add to local.properties: {var_name}=your-actual-key, OR  
2. Ensure it's already exposed in build.gradle buildConfigField
Then run this command again"""

def find_in_local_properties(var_name):
    """Find a variable in local.properties"""
    local_props = Path("local.properties")
    if not local_props.exists():
        return None
    
    try:
        content = local_props.read_text()
        # Look for VARIABLE_NAME=value
        pattern = rf'^{re.escape(var_name)}\s*=\s*(.+)$'
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1).strip().strip('"').strip("'")
    except Exception:
        pass
    
    return None

def store_in_local_properties(var_name, value):
    """Store a variable in local.properties securely"""
    local_props = Path("local.properties")
    
    # Read existing content
    if local_props.exists():
        content = local_props.read_text()
        lines = content.split('\n')
    else:
        lines = []
    
    # Check if variable already exists
    var_exists = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{var_name}="):
            lines[i] = f"{var_name}={value}"
            var_exists = True
            break
    
    # Add if doesn't exist
    if not var_exists:
        if lines and not lines[-1].strip():
            lines[-1] = f"{var_name}={value}"
        else:
            lines.append(f"{var_name}={value}")
    
    # Write back
    local_props.write_text('\n'.join(lines))
    
    # Make sure local.properties is in .gitignore
    ensure_gitignore_has_local_properties()

def ensure_gitignore_has_local_properties():
    """Ensure local.properties is in .gitignore for security"""
    gitignore = Path(".gitignore")
    
    if gitignore.exists():
        content = gitignore.read_text()
        if "local.properties" not in content:
            gitignore.write_text(content + "\nlocal.properties\n")
    else:
        gitignore.write_text("local.properties\n")

def is_buildconfig_variable_exposed(var_name):
    """Check if a variable is exposed in BuildConfig (comprehensive)"""
    target = GRADLE_KTS if GRADLE_KTS.exists() else GRADLE_GROOVY
    if not target.exists():
        return False
    
    content = target.read_text()
    
    # Look for various buildConfigField patterns:
    patterns = [
        # Standard buildConfigField
        rf'buildConfigField.*["\']String["\'].*["\']?{re.escape(var_name)}["\']?',
        # With project.findProperty
        rf'buildConfigField.*["\']String["\'].*["\']?{re.escape(var_name)}["\']?.*findProperty',
        # Environment variable reference
        rf'buildConfigField.*["\']String["\'].*["\']?{re.escape(var_name)}["\']?.*System\.getenv',
        # Direct value assignment
        rf'buildConfigField.*["\']String["\'].*["\']?{re.escape(var_name)}["\']?.*["\'].*["\']',
    ]
    
    for pattern in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    
    return False

def expose_in_buildconfig(var_name):
    """Expose a local.properties variable in BuildConfig"""
    target = GRADLE_KTS if GRADLE_KTS.exists() else GRADLE_GROOVY
    if not target.exists():
        return False
    
    content = target.read_text()
    
    # Check if already exposed
    if is_buildconfig_variable_exposed(var_name):
        return True
    
    # Add buildConfigField
    if target.suffix == ".kts":
        build_config_line = f'        buildConfigField("String", "{var_name}", "\\"${{project.findProperty(\\"{var_name}\\") ?: \\"\\"}}\\")'
    else:
        build_config_line = f'        buildConfigField "String", "{var_name}", "\\"${{project.findProperty(\\"{var_name}\\") ?: \\"\\"}}\\"'
    
    # Find android block and add buildConfigField
    android_pattern = r'android\s*{'
    match = re.search(android_pattern, content)
    
    if match:
        # Look for existing defaultConfig block
        default_config_pattern = r'(defaultConfig\s*{[^}]*})'
        default_config_match = re.search(default_config_pattern, content, re.DOTALL)
        
        if default_config_match:
            # Add inside defaultConfig block
            default_config_content = default_config_match.group(1)
            # Insert before the closing brace
            new_default_config = default_config_content[:-1] + f'\n{build_config_line}\n    }}'
            new_content = content.replace(default_config_content, new_default_config)
        else:
            # Add defaultConfig block after android {
            insert_pos = match.end()
            new_content = (content[:insert_pos] + 
                          f'\n    defaultConfig {{\n{build_config_line}\n    }}\n' + 
                          content[insert_pos:])
        
        target.write_text(new_content)
        return True
    
    return False

# ---------- application/activity finding functions ----------
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

def inject_init(app_key_input):
    """Updated inject_init with proper app key handling"""
    
    # Handle the app key properly
    if not app_key_input or app_key_input.strip() == "":
        app_key_result = handle_no_key_provided()
        if app_key_result.startswith("⚠️"):
            return app_key_result
        app_key_expr = app_key_result
    else:
        app_key_expr = handle_app_key(app_key_input)
        if app_key_expr.startswith("⚠️"):
            return app_key_expr
    
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
                        "description": "Reference used in code – e.g. BuildConfig.UXCAM_KEY, UXCAM_KEY, or actual key"
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
        app_key_ref = arguments.get("appKeyRef", "")  # Empty default instead of assuming
        
        reports = [
            add_repo(),
            add_dependency(),
            inject_init(app_key_ref)  # Now handles empty/invalid keys properly
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