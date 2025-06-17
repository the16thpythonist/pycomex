# Plugin Hooks

This page aims to provide a (non-exhaustive) list of the available hooks in the pycomex library. Each hook is described with its name, a brief description, and the parameters it accepts.

### 🪝 `plugin_registered`

This hook is executed *right* after a plugin is registerd. The hook receives the name of the plugin that was registered as well as the plugin object itself. This hook can for example be used to hot-swap or replace certain plugins with newer or alternative versions.

| Parameter | Description                |
|-----------|----------------------------|
| `name` | The name of the plugin that was registered |
| `plugin` | The `Plugin` object instance that was registered |
| `config` | The `Config` instance that is used by the pycomex library |

Returns: None

---

### 🪝 `plugin_registered__{plugin_name}`

This hook is executed right after a plugin is registered. The name of the hook is dynamically derived from the name of the actual plugin. Therefore, only the plugin itself will likely be able to know the name of this hook and be able to register a function to it.

| Parameter | Description                |
|-----------|----------------------------|
| `plugin` | The `Plugin` object instance that was registered |
| `config` | The `Config` instance that is used by the pycomex library |


## `Experiment` Hooks

---

### 🪝 `before_experiment_parameters`

This hook is executed within the lifetime of an `Experiment` instance after its construction - right before the experiment parameters are processed. 

| Parameter | Description                |
|-----------|----------------------------|
| `experiment` | The `Experiment` instance itself |


### 🪝 `experiment_constructed`

This hook is executed at the end of the `Experiment` constructor. It can be used
to perform additional setup steps once the experiment object exists.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance that was created |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `after_experiment_initialize`

Executed after the `Experiment.initialize` method completed. At this point the
archive folder has been created and the experiment is ready to run.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `after_experiment_finalize`

Executed after the `Experiment.finalize` method completed. This allows for
additional cleanup or post-processing once the experiment is finished.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_fig`

Called at the end of `Experiment.commit_fig` after the figure has been saved to
the archive folder.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved figure file |
| `figure` | The `matplotlib` figure instance |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_json`

Called at the end of `Experiment.commit_json` once the JSON file has been
written.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved JSON file |
| `data` | The original data structure that was saved |
| `content` | The string representation that was written to the file |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_commit_raw`

Called at the end of `Experiment.commit_raw` after the text file has been
created.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | The name of the saved file |
| `content` | The text content that was written |
| `config` | The `Config` instance that is used by the pycomex library |


### 🪝 `experiment_track`

Called at the end of `Experiment.track`. It receives the tracked name and value
so that the tracking information can be forwarded to external services.

| Parameter | Description |
|-----------|-------------|
| `experiment` | The `Experiment` instance itself |
| `name` | Name under which the value was tracked |
| `value` | The tracked value or figure |
| `config` | The `Config` instance that is used by the pycomex library |


---

## `Config` Hooks

---

### 🪝 `after_plugins_loaded`

This hook is executed right after the plugins are loaded and before the configuration is finalized. This is one of the earliest possible entry points for any plugin and could for example be used for some early initialization tasks.

| Parameter | Description                |
|-----------|----------------------------|
| `config` | The `Config` instance itself     |
| `plugins` | A dictionary where the string keys are the plugin names and the values are the corresponding `Plugin` object instances |

