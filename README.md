# UnityBundleExtractor

A robust Python script for extracting various assets from Unity3D bundle files. Features intelligent naming, structured output, and comprehensive logging for efficient game asset extraction.

## Features

  * **Broad Asset Type Support**: Capable of extracting a wide array of Unity asset types, including but not limited to:
      * `Texture2D`, `Sprite` (images)
      * `TextAsset` (text, JSON, configuration files)
      * `AudioClip` (audio files, WAV/OGG)
      * `Mesh`, `Material`, `Shader` (3D model components)
      * `AnimationClip`, `Animator`, `AnimatorController`, `AnimatorOverrideController` (animation data)
      * `Font` (font files)
      * `Prefab`, `Scene`, `GameObject`, `Transform` (scene and object structures)
      * Various components and settings: `MonoBehaviour`, `MonoScript`, `Camera`, `Light`, `Colliders`, `Rigidbody`, `Canvas`, `ParticleSystem`, `RenderSettings`, `PlayerSettings`, etc.
  * **Intelligent File Naming**: Implements an advanced algorithm to automatically derive meaningful filenames from asset attributes (`name`, `m_Name`, `m_ClassName`, etc.), significantly reducing "Unnamed" files.
  * **Structured Output**: Organizes extracted assets into type-specific subdirectories (e.g., `output_folder/Texture2D/`, `output_folder/MonoBehaviour/`).
  * **Comprehensive Logging**: Generates a detailed `extraction_log.txt` file in the output directory, providing:
      * Summary of processed, successful, and failed extractions.
      * Counts of each extracted asset type.
      * Specific error details for problematic assets, including object ID, type, error message, and traceback (if available).
  * **Robust Error Handling**: Designed to gracefully handle various extraction failures (e.g., missing attributes, decoding issues, corrupted data) by attempting fallback extraction methods (e.g., saving basic JSON fields or raw binary/text) to maximize data recovery.
  * **User-Friendly Interface**: Simple command-line prompts for input bundle path and output directory.

## Disclaimer

This tool is provided for **educational and research purposes only**. It is intended to help developers, researchers, and enthusiasts understand the structure of Unity game assets and facilitate legitimate modding, analysis, or asset recovery for **personal projects where legal permissions are obtained**.

**The use of this tool for illegal activities, copyright infringement, reverse engineering of proprietary software without permission, or any other unauthorized commercial exploitation is strictly prohibited.** The creator and maintainers of this repository are not responsible for any misuse or damage caused by the use of this tool. Users are solely responsible for ensuring their actions comply with all applicable laws and licenses.

## Requirements

To run this script, you need to have Python installed on your system (Python 3.7+ is recommended).
The following Python libraries are required:

  * `UnityPy`
  * `tqdm`

You can install these dependencies using pip:

```bash
pip install -r requirements.txt
```
or
```bash
python -m pip install -r requirements.txt
```

### `requirements.txt` content:

```
UnityPy
tqdm
```

## How to Use

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/lenzarchive/UnityBundleExtractor.git
    cd UnityBundleExtractor
    ```

    (Replace `https://github.com/lenzarchive/UnityBundleExtractor.git` with the actual URL of your repository.)

2.  **Install dependencies**:
    Ensure you have pip installed, then run:

    ```bash
    pip install -r requirements.txt
    ```
    or
    ```bash
    python -m pip install -r requirements.txt
    ```

4.  **Run the script**:

    ```bash
    python main.py
    ```

5.  **Provide inputs**:
    The script will prompt you to enter the full path to your Unity `.bundle` file and the desired output folder path.

    ```
    Please enter the .bundle file path: D:\path\to\your\bundle\file.bundle
    Please enter the output folder path: D:\output\extracted_assets
    ```

6.  **Monitor extraction**:
    A progress bar will appear, showing the extraction progress. Any critical errors will be displayed in the console.

7.  **Check results**:
    Once the extraction is complete, your extracted assets will be organized into subfolders within the specified output directory (e.g., `D:\output\extracted_assets\Texture2D\`, `D:\output\extracted_assets\MonoBehaviour_basic.json`).
    A detailed `extraction_log.txt` file will also be generated in the output directory, which is crucial for reviewing extraction status and any encountered issues.

## Known Issues and Troubleshooting

  * **`FileNotFoundError: [WinError 3] The system cannot find the path specified: ''`**: This error occurs if the bundle file path or output directory path is left empty during input. Ensure you provide valid, non-empty paths.
  * **`AttributeError: 'MonoBehaviour' object has no attribute 'read_typetree'`**: This is a common challenge with `MonoBehaviour` assets, as their full structure often depends on associated Unity C\# scripts that might not be easily parsable outside the Unity editor. The script attempts to extract basic fields (`_basic.json`) as a robust fallback.
  * **`NoneType: None` or `UnicodeEncodeError` in logs**: These indicate that some asset data was either empty/corrupted or contained characters that couldn't be encoded. The script uses robust error handling (`errors="replace"`) to prevent crashes, but such assets might only be saved as generic `.txt` or `.bin` files for manual inspection.
  * **Some files still named `Unnamed_...`**: While the naming algorithm is advanced, certain Unity assets genuinely lack accessible name attributes within their raw data. In such rare cases, a `Unnamed_PathID` fallback is used.
  * **Incomplete Data for Complex Assets**: For very complex or custom Unity asset types, `UnityPy` might not be able to fully parse their internal structure. In these cases, the script will attempt to save the raw data (`.bin`) or a string representation (`.txt`) for further investigation.

## Contributing

Encountered a bug? Have an idea for a new feature or an improvement to the extraction algorithm?
We welcome contributions\! Please feel free to:

1.  **Open an Issue**: Describe the bug you found (with reproduction steps if possible) or suggest a new feature.
2.  **Submit a Pull Request**: Fork this repository, make your changes, and then submit a pull request.

Your contributions help make this tool better for everyone\!

## Credit

Thanks for using this script\!
Credit: [@lenzarchive](https://github.com/lenzarchive)

## License

This script is licensed under the MIT License. See the `LICENSE` file for more details.

-----
