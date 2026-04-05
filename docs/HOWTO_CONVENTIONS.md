# How-To Conventions

From this point onward, all project setup and operational instructions should follow these rules:

1. **Every step must include explicit commands.**
2. **Commands must target the real local project path:** `D:\WOW\wm-project`
3. **Windows-first instructions use PowerShell unless stated otherwise.**
4. **Verification steps must also include commands**, not only prose like "check that it exists".
5. **Placeholders must be clearly labeled** when manual replacement is required.

## Required format for future guides

Each how-to should be written in this shape:

### Step N — what this step does
Short explanation.

```powershell
# exact commands here
```

### Verify
```powershell
# exact verification commands here
```

## Canonical local path

Use this path in examples unless the user says otherwise:

```text
D:\WOW\wm-project
```

## Example

### Step 1 — open the project directory

```powershell
cd D:\WOW\wm-project
```

### Verify

```powershell
Get-Location
```
