# Third-party notices

The sections below the line cover libraries compiled into the app's web UI. The
Windows installer additionally ships these components unmodified, each under its
own licence (see "Components bundled with the Windows installer").

## Fabric.js

Storyboarder's native drawing canvas uses
[`Fabric.js`](https://github.com/fabricjs/fabric.js), version 7.4.0.

MIT License

Copyright (c) 2008-2015 Printio (Juriy Zaytsev, Maxim Chernyak)

Copyright (c) 2016-present Andrea Bogazzi, Shachar Nen and Fabric.js contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## perfect-freehand

Storyboarder's freehand ink and marker strokes use
[`perfect-freehand`](https://github.com/steveruizok/perfect-freehand), version 1.2.3.

MIT License

Copyright (c) 2021 Stephen Ruiz Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

# Components bundled with the Windows installer

The Nihilux installer (`packaging/stage.ps1`) bundles the following, unmodified.
Their licence texts are installed next to them.

## FFmpeg (ffmpeg.exe, ffprobe.exe and their DLLs)

`app/bin/` contains an LGPL build of [FFmpeg](https://ffmpeg.org) 8.1
(`ffmpeg-n8.1.3-24-g92611900bb-win64-lgpl-shared-8.1`, built by
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds)), configured with
`--enable-version3 --enable-shared` and without `--enable-gpl` or `--enable-nonfree`.
It is licensed under the **GNU Lesser General Public License, version 3 or later**;
the licence text is `app/bin/FFMPEG-LICENSE.txt`.

- Nihilux runs `ffmpeg.exe` and `ffprobe.exe` as separate programs and does not link to
  them. The FFmpeg libraries are shared DLLs and can be replaced by the user with
  another compatible build.
- The corresponding source code is available from
  <https://github.com/FFmpeg/FFmpeg> at the tag/commit named in the build name, and
  the build scripts from <https://github.com/BtbN/FFmpeg-Builds>.
- The build includes third-party libraries (for example OpenH264, dav1d, libvpx, opus,
  libass, freetype, harfbuzz); their licences are those of the respective projects. H.264
  encoding in the installed app uses OpenH264 (BSD-2-Clause) compiled into FFmpeg; this
  is not Cisco's binary distribution, so Cisco's patent licence for its OpenH264
  binaries does not apply to it.

## Python

`python/` is CPython 3.14 from
[python-build-standalone](https://github.com/astral-sh/python-build-standalone)
(Python Software Foundation License; `python/LICENSE.txt` also lists the licences of
the libraries CPython includes, such as OpenSSL, SQLite, zlib, libffi, Tcl/Tk and XZ).

## Python packages

Installed into `python/Lib/site-packages` from `requirements.lock.txt` (exact
versions in `app/requirements.runtime.txt`); each package's licence is in its
`*.dist-info` folder. Main packages and licences:

| Package | Licence |
| --- | --- |
| FastAPI, Pydantic, pydantic-core, AnyIO, attrs, cffi, comfy-sdk, httptools, psd-tools, PyYAML, watchfiles | MIT |
| Starlette, Uvicorn, HTTPX, httpcore, Click, websockets, NumPy | BSD-3-Clause (NumPy bundles further permissive licences: 0BSD, MIT, Zlib, CC0) |
| Pillow | MIT-CMU (HPND) |
| opencv-python-headless | Apache-2.0 (bundles FFmpeg as LGPL-2.1 shared libraries and other libraries listed in its dist-info) |
| python-multipart | Apache-2.0 |
| ReportLab | BSD |
| keyring, jaraco.*, more-itertools | MIT |
| blake3 | CC0-1.0 or Apache-2.0 |
| certifi | MPL-2.0 |
| idna, charset-normalizer, typing-extensions, h11, colorama, packaging | BSD / MIT / PSF / Apache-2.0 as stated in each package |

## Desktop shell

The shell is built with [Tauri](https://tauri.app) (MIT or Apache-2.0) and its Rust
dependencies (MIT and/or Apache-2.0 in the vast majority; see
`desktop/src-tauri/Cargo.lock`). It uses Microsoft Edge WebView2, which the installer
installs from Microsoft if it is missing.
