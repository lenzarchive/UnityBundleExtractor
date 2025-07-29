# UnityBundleExtractor

A robust Python script for extracting various assets from Unity3D bundle files. Features intelligent naming, structured output, and comprehensive logging for efficient game asset extraction.

## Features

* **Multiple Operating Modes**: Run the script in different ways to suit your needs.
    * **Interactive Mode**: The default mode for guided, single-file extraction.
    * **Batch Mode (`--batch`)**: Automatically find and process all bundle files within a specified folder.
    * **Info Mode (`--info`)**: Quickly analyze and display a bundle's contents and metadata without extracting any files.
    * **Debug Mode (`--debug`)**: Provides verbose console output for development and troubleshooting.

* **Deep Metadata Extraction**: Generates additional files for in-depth analysis of the bundle's structure:
    * `bundle_metadata.json`: Contains general information about the bundle, including Unity version, platform, and container paths.
    * `type_tree.json`: Provides detailed type information for every object within the bundle.
    * `dependencies.json`: Maps out the relationships and dependencies between different assets.

* **Advanced Asset Processing**: Goes beyond simple data dumping for key asset types:
    * **`Mesh`**: Extracts geometry into a standard `.obj` file, ready for use in 3D modeling software, and includes a detailed `_info.json`.
    * **`Material` & `AnimationClip`**: Parses complex properties, textures, and keyframes into structured `.json` files.
    * **`Texture2D` & `Sprite`**: Saves images as `.png` and creates an `_info.json` file with metadata like dimensions, format, and sprite rects.
    * **`AudioClip`**: Extracts audio data to `.wav` or `.ogg` and saves an `_info.json` file with format details like frequency and channels.

* **Broad Asset Type Support**: Capable of extracting a wide array of Unity asset types, including but not limited to:
    * `Texture2D`, `Sprite` (images)
    * `TextAsset` (text, JSON, configuration files)
    * `AudioClip` (audio files)
    * `Mesh`, `Material`, `Shader` (3D model components)
    * `AnimationClip`, `Animator`, `AnimatorController` (animation data)
    * `Font` (font files)
    * `Prefab`, `Scene`, `GameObject`, `Transform` (scene and object structures)
    * `MonoBehaviour`, `MonoScript`, and various other components and settings.

* **Intelligent File Naming**: Implements an advanced algorithm to derive meaningful filenames from asset attributes and parent `GameObject` names, significantly reducing "Unnamed" files.

* **Structured Output**: Organizes extracted assets into type-specific subdirectories (e.g., `output_folder/Texture2D/`, `output_folder/MonoBehaviour/`).

* **Comprehensive Logging**: Generates a detailed `extraction_log.txt` with a summary, asset type counts, and specific error details with tracebacks for any problematic assets.

* **Robust Error Handling**: Gracefully handles extraction failures by attempting fallbacks (e.g., saving basic fields, serializing to JSON, or saving raw data) to maximize data recovery.

## Disclaimer

This tool is provided for **educational and research purposes only**. It is intended to help developers, researchers, and enthusiasts understand the structure of Unity game assets and facilitate legitimate modding, analysis, or asset recovery for **personal projects where legal permissions are obtained**.

## Requirements

To run this script, you need Python 3.7+ installed. The following Python libraries are required:

* `UnityPy`
* `tqdm`
* `lz4`

You can install these dependencies using pip:

```bash
pip install -r requirements.txt
```
or
```bash
python -m pip install -r requirements.txt
```

### `requirements.txt` content:

```requirements
UnityPy
tqdm
lz4
```

## How to Use

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/lenzarchive/UnityBundleExtractor.git
    cd UnityBundleExtractor
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the script in your desired mode**:

    * **For standard interactive extraction**:
        ```bash
        python main.py
        ```
        The script will then prompt you to enter the bundle file path and output directory.
        ```output
        Please enter the .bundle file path: C:\path\to\your\bundle\file.bundle
        Please enter the output folder path: C:\output\extracted_assets
        ```

    * **For batch processing a whole folder**:
        ```bash
        python main.py --batch
        ```
        The script will ask for the folder containing your bundles and a base output directory.

    * **To view bundle information without extracting**:
        ```bash
        python main.py --info
        ```
        The script will ask for the path to the bundle file you want to analyze.

4.  **Monitor extraction**:
    A progress bar will show the extraction progress.

5.  **Check results**:
    Once complete, your extracted assets will be in the specified output directory, organized into subfolders. You will also find the log and metadata files (`extraction_log.txt`, `bundle_metadata.json`, `type_tree.json`, etc.) in the root of the output folder.

## Known Issues and Troubleshooting

* **Some files still named `Unnamed_...`**: While the naming algorithm is advanced, some assets genuinely lack accessible name attributes. In these cases, a fallback name based on object type and path ID is used.

## Contributing

Encountered a bug? Have an idea for a new feature? We welcome contributions! Please feel free to:

1.  **Open an Issue**: Describe the bug or suggest a new feature.
2.  **Submit a Pull Request**: Fork the repository, make your changes, and submit a pull request.

Your contributions help make this tool better for everyone!

## Credit

Thanks for using this script!
Credit: [@alwizba](https://github.com/lenzarchive)

## License

This script is licensed under the MIT License. See the `LICENSE` file for more details.
