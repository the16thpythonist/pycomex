# Reproducible Experiments

## Status

in progress

## Context

The main motivation for this feature is the ongoing reproducibility crisis in science where many scientific findings cannot be reproduced by other researchers. Not only that but sometimes one cant even get the code of others to run in the first place because the dependencies were not pinned correctly, or some dependencies are missing or incompatible etc. In general, a lot of research code does not work outside the original environment it was developed in. This is a huge problem for the scientific community because it hinders the progress of science and makes it difficult to build upon previous work.

What would be needed, therefore, is some kind of simple solution which hides away all of the complexity of setting up a reproducible environment and just works out of the box. This is where the reproducible mode of pycomex comes into play.

## Decision

The decision is to implement a "reproducible mode" in pycomex which, when enabled, will automatically bundle the environment information into the experiment archive artifact with the end goal of being able to reproduce / re-run exactly that computational experiment by running a single command.

```bash
pycomex reproduce path/to/experiment/archive.zip
```

And that archive contains ALL of the information needed to set up the environment again. This includes automatic export of all of the exact library versions that were used during the experiment run, the python version, the operating system information and a copy of all the used local files (scripts, modules, data files etc).

## Implementation

The reproducible mode is activated by setting the special parameter `__REPRODUCIBLE__ = True` in an experiment module. When enabled, the `finalize_reproducible()` method is automatically called at the end of experiment execution to capture the complete runtime environment.

### Architecture

The implementation consists of several key components:

#### 1. Dependency Tracking (`pycomex/util.py:771-827`)

The `get_dependencies()` function captures comprehensive information about all installed Python packages:

- **Package Metadata**: Name, version, installation path, requirements list
- **Editable Detection**: Identifies packages installed in editable/development mode via PEP 610 `direct_url.json`
- **Package Source**: Filesystem paths for both regular and editable installations
- Uses `importlib.metadata.distributions()` for reliable package discovery

Returns a dictionary with package names as keys and metadata dictionaries as values.

#### 2. Python Environment Capture (`pycomex/functional/experiment.py:1062-1070`)

Python version information is stored in the special `__python__` key:

```python
dependencies["__python__"] = {
    "version": "3.10.12",
    "version_info": {"major": 3, "minor": 10, "micro": 12},
    "version_string": "3.10.12 (main, Nov 20 2023, 15:14:05) [GCC 11.4.0]"
}
```

This enables reproduction with the exact Python version.

#### 3. System Environment Capture (`pycomex/util.py:726-768`)

The `get_environment_info()` function captures system-level details stored in the `__environment__` key:

- **Operating System**: Name, version, platform, architecture
- **Environment Variables**: Critical variables (PATH, PYTHONPATH, CUDA_HOME, LD_LIBRARY_PATH, etc.)
- **System Libraries**: CUDA version detection via nvidia-smi
- **Hardware Context**: Platform architecture (x86_64, arm64, etc.)

#### 4. Source Code Export (`pycomex/functional/experiment.py:1082-1110`)

For packages installed in editable mode (typically local development packages):

- Creates `.sources/` directory in experiment archive
- Uses `uv build --sdist` to generate source distribution tarballs
- Captures exact code state at experiment runtime
- Enables installation from local source later

#### 5. Storage Format

All reproducibility information is saved to `.dependencies.json` in the experiment archive:

```json
{
    "package-name": {
        "name": "package-name",
        "version": "1.2.3",
        "path": "/path/to/package",
        "requires": ["dep1>=1.0", "dep2"],
        "editable": false
    },
    "__python__": { "version": "3.10.12", ... },
    "__environment__": { "os": {...}, "env_vars": {...}, "system_libraries": {...} }
}
```

Source tarballs for editable packages are stored in `.sources/*.tar.gz`.

#### 6. CLI Support (`pycomex/cli/` package)

The `pycomex reproduce` command (implemented in `pycomex/cli/commands/run.py`) provides:

- Archive validation and dependency loading
- Python version extraction and virtual environment creation
- Environment comparison UI (rich panels showing original vs current)
- Difference detection and highlighting for OS, CUDA, environment variables
- Automated dependency installation workflow

#### 7. Testing (`tests/test_functional_reproducibility.py`)

Comprehensive test coverage includes:

- Unit tests for `finalize_reproducible()` method
- Dependency file creation and structure validation
- Python version and environment info capture
- Source code export for editable packages
- Integration tests for full reproducibility pipeline
- Parameter restoration and archive loading
- Non-JSON serializable parameter handling

### Workflow

1. **Experiment Setup**: User sets `__REPRODUCIBLE__ = True`
2. **Normal Execution**: Experiment runs normally, parameters and data saved as usual
3. **Finalization Hook**: At experiment end, `finalize_reproducible()` is called
4. **Dependency Capture**: All packages, Python version, environment info collected
5. **Source Export**: Editable packages built as source distributions
6. **Archive Creation**: Complete archive with code, data, logs, and reproducibility info
7. **Reproduction**: Use `pycomex reproduce <archive>` to recreate environment and re-run

## TODO

The following improvements are organized by priority based on impact and user value.

### High Priority - Core Reproducibility Features

These features are essential for a complete, production-ready reproducibility system:

#### 1. Requirements File Generation

**Goal**: Auto-generate standard requirements files from captured dependencies.

- Generate `requirements.txt` with pinned versions (`package==1.2.3`)
- Support `pyproject.toml` for modern Python projects
- Optional conda `environment.yml` generation
- Include both direct and transitive dependencies with clear separation
- Handle platform-specific dependencies appropriately

**Value**: Makes reproduction simpler and more portable across different systems and tooling.

#### 2. Complete Reproduction Workflow

**Goal**: Finish implementing the `pycomex reproduce` command for full automation.

- Automated virtual environment creation with correct Python version
- Dependency installation from captured requirements
- Source package installation from `.sources/` directory
- Environment variable setup from captured config
- Execute experiment in reproduced environment with parameter restoration
- Report any differences or warnings

**Value**: End-to-end automation is the killer feature that delivers on the reproducibility promise.

#### 3. Git Integration

**Goal**: Capture version control state as part of reproducibility context.

- Detect if experiment is in a git repository
- Capture commit hash, branch name, remote URL, tags
- Detect and warn about uncommitted changes (dirty working tree)
- Save `git diff` output for dirty repositories
- Store git information in `.dependencies.json` under `__git__` key
- Option to enforce clean git state for reproducible mode

**Value**: Code state is critical for reproducibility; git provides the authoritative source of truth.

#### 4. Non-Reproducibility Detection

**Goal**: Proactive analysis to identify potential reproducibility issues.

- Static analysis to detect non-deterministic patterns:
  - Missing random seeds (numpy, random, torch, tensorflow)
  - Use of `datetime.now()` without explicit timezone
  - Hard-coded absolute paths
  - Environment variable dependencies without defaults
- Runtime warnings for detected issues
- Reproducibility checklist in experiment metadata
- Optional strict mode to fail on detected issues

**Value**: Prevention is better than cure; catch issues before they cause problems.

#### 5. Docker/Container Generation

**Goal**: Generate containerized environments for ultimate reproducibility.

- Auto-generate Dockerfile from reproducibility information
- Include base image matching OS and architecture
- Python version installation and configuration
- System library dependencies (CUDA, etc.)
- Python package installation
- Experiment execution as default command
- Option to build and export Docker image
- Support for alternative container formats (Singularity/Apptainer for HPC)

**Value**: Containers provide complete isolation and the highest level of reproducibility across different systems.

### Medium Priority - Enhanced Capabilities

These features significantly improve the reproducibility system but are not essential for core functionality:

#### 6. Selective Dependency Export

**Goal**: Fine-grained control over which dependencies are captured.

- Option to export only direct dependencies vs. all packages
- Configurable dependency depth for transitive dependencies
- Exclude lists for development tools (pytest, black, mypy, etc.)
- Include lists for critical packages
- Automatic detection of experiment-specific dependencies via import analysis

**Value**: Reduces archive size and focuses on essentials, improving portability.

#### 7. Extended Hardware Information

**Goal**: Capture hardware context for hardware-sensitive experiments.

- GPU details: Model name, memory, CUDA compute capability, driver version
- CPU information: Model, architecture, core count, features (AVX, SSE)
- System memory (total RAM, available)
- Disk information (type, speed) where applicable
- Store in `__hardware__` key

**Value**: Some experiments (ML training, numerical simulations) are hardware-sensitive.

#### 8. Data Provenance Tracking

**Goal**: Track input data files as part of reproducibility.

- Capture checksums (SHA-256) of input data files
- Track data file locations and versions
- Enhanced integration with `CopiedPath` parameter type
- Data manifest file listing all input files
- Validation of data integrity on reproduction
- Optional data archiving within experiment archive

**Value**: Data is as important as code for reproducibility; track it explicitly.

#### 9. Reproducibility Report/Score

**Goal**: Quantify and report reproducibility quality.

- Generate comprehensive reproducibility report
- Reproducibility score (0-100%) based on completeness
- Checklist of captured elements:
  - ✓ Python version captured
  - ✓ Dependencies exported
  - ✓ Source code archived
  - ✗ Git state not captured
  - ⚠ Uncommitted changes detected
- Highlight missing or problematic elements
- Actionable suggestions for improvement
- Export report as Markdown/HTML

**Value**: Provides actionable feedback and encourages best practices.

#### 10. System-Level Dependencies

**Goal**: Track OS packages and system libraries.

- Detect installed OS packages (apt, yum, brew, pacman)
- Identify system libraries (OpenBLAS, MKL, LAPACK, etc.)
- Track shared library versions (ldd output for key binaries)
- Store in `__system_packages__` key
- Generate installation scripts for system packages

**Value**: Python packages often depend on system libraries; explicit tracking prevents "works on my machine" issues.

#### 11. Automated Documentation

**Goal**: Generate human-readable reproducibility documentation.

- Extract reproducibility information from archive
- Generate setup instructions (step-by-step)
- Environment specification in prose
- Dependency list with rationale
- Export to multiple formats (Markdown, HTML, PDF)
- Include in experiment archive as `REPRODUCIBILITY.md`

**Value**: Makes sharing results easier and improves accessibility for non-technical users.

### Low Priority - Nice-to-Have Features

These features add value but are not critical for most users:

#### 12. Cloud Storage Integration

**Goal**: Enable remote storage and sharing of reproducible archives.

- Upload/download archives to cloud storage (S3, GCS, Azure Blob, Dropbox)
- Share experiments via URLs
- Version control for experiment archives
- Metadata indexing for search
- Integration with experiment tracking platforms (MLflow, W&B)

**Value**: Enables collaboration and long-term storage beyond local filesystems.

#### 13. Archive Comparison Tools

**Goal**: Compare two experiment archives to understand differences.

- Side-by-side comparison of two archives
- Highlight dependency version differences
- Environment drift detection
- Parameter differences
- Rich visual diff output

**Value**: Useful for debugging reproducibility failures and understanding result variations.

#### 14. Version Pinning Strategies

**Goal**: Flexible dependency version specifications.

- Configurable pinning strategies:
  - Exact (`package==1.2.3`)
  - Compatible (`package~=1.2.0`)
  - Minimum (`package>=1.2.0`)
- Different strategies for different dependency types
- Balance reproducibility vs. flexibility
- Security update consideration

**Value**: Provides flexibility for different use cases and security requirements.

#### 15. Dependency Visualization

**Goal**: Visual representation of dependency relationships.

- Generate dependency graph (networkx + graphviz)
- Show dependency tree with versions
- Highlight editable vs installed packages
- Color-code by category (core, dev, optional)
- Interactive web-based explorer
- Export as PNG/SVG

**Value**: Understanding complex dependency relationships, especially for debugging.

#### 16. License Compliance

**Goal**: Track and report software licenses.

- Capture package licenses from metadata
- Detect potential license conflicts
- Generate comprehensive license report
- Export for publication compliance
- Warn about incompatible license combinations
- Support for academic vs commercial use cases

**Value**: Important for commercial applications and academic publications with licensing requirements.

#### 17. Temporal Snapshots

**Goal**: Handle packages removed or changed on PyPI.

- Query PyPI for exact package states at experiment time
- Store package metadata even for removed packages
- Link to archives or mirrors
- Fallback strategies for unavailable packages

**Value**: Long-term reproducibility when packages disappear from PyPI.

### Conclusion

The reproducible mode feature represents a significant step toward solving the reproducibility crisis in computational research. While it adds some complexity and has certain limitations, the benefits far outweigh the costs. The current implementation provides a solid foundation with room for enhancement through the prioritized TODO items.

The feature aligns with PyComex's philosophy of making computational experiments self-documenting and easily analyzable while requiring minimal additional effort from users. As the feature matures and the TODO items are implemented, PyComex will provide one of the most comprehensive reproducibility solutions in the Python ecosystem.