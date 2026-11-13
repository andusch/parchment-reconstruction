# Public-corpus pilot

- Status: Working note. Partial answer to [Q-SCI-15](EVALUATION.md#q-sci-15) for the candidate set below.
- Reviewed: 8 November 2026, from the terms pages linked in each section.
- Glossary: [DATA_MODEL.md](DATA_MODEL.md#glossary)
- Open-question index: [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)

This note names three published sources an operator may download, store outside Git, and checksum locally. It is the license review for that candidate set. It leaves [Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) open for every other corpus and for any accuracy claim on real images.

The operator downloads these files in a browser or another client of their own. [ADR-0001](adr/0001-local-only-processing.md) still forbids a network call from the program.

## Scope

The pilot is physical imagery. A museum catalogue title, culture, geography, script, or transcription stays on the institution's page. This note does not import that text as observed evidence, as a reading, or as a find-site. Ancient Greek hand-transcription, Black Sea or any other site identity, and local HTR stay out of scope. P5 remains blocked by [Q-SCI-14](OPEN_QUESTIONS.md#q-sci-14).

Re-read the terms URL on the day of download. If that page no longer states the license recorded here, leave the file out of the pilot.

## Where the files live

Keep the directory outside the checkout. [Using the workbench](USAGE.md) uses the same pattern for synthetic leaves. The durable directory, the `prw verify` sequence, and the scale lines are [Public import path](pilot-import-path.md). The `$TMPDIR` path below is a one-session checksum. A path inside the repository, including `data/`, `scans/`, and `real_data/`, is the wrong place. [`.gitignore`](../.gitignore) ignores `*.tif` and `*.tiff`. That exclusion is not permission to force-add a file. [Security and privacy](SECURITY_AND_PRIVACY.md) treats an accidental commit as a standing risk.

```bash
PILOT="${TMPDIR:-/tmp}/prw-pilot-corpus"
mkdir -p "$PILOT/downloads"
```

For each file, write a text sidecar beside it. The sidecar is an operator note. It is not a provenance envelope, not a `BenchmarkLabel`, and not a project record. [Q-ENG-01](OPEN_QUESTIONS.md#q-eng-01) is open, and the CLI does not write `manifest.json` or `originals/`. Suggested fields:

- source name
- object or file URL
- terms URL
- license string copied from that page
- date the terms page was read
- `sha256:` plus the lowercase hexadecimal digest of the unchanged bytes
- attribution line when the license requires one, or `absent` when it does not

Leave the downloaded bytes unchanged. CC0 would allow redistribution. This repository still refuses the files. Do not place the directory under a cloud-sync folder when the copy should stay on the machine. [Q-PRI-01](SECURITY_AND_PRIVACY.md#q-pri-01) remains open.

`prw verify` accepts a file whose first four bytes are `II*\x00` or `MM\x00*` and records media type `image/tiff`. Any other prefix is an unsupported media type. The command hashes bytes. It does not decode pixels.

```bash
uv run prw verify "$PILOT/downloads/object.tif" --expected "sha256:…"
```

`prw verify` checksums a classic TIFF and does not decode it. Pixel commands read a lossless master that is not the synthetic fixture layout with decoder `lossless_tiff` version `1` ([ADR-0014](adr/0014-stdlib-lossless-tiff.md)). A file that decoder refuses does not become an outline. Do not write these downloads into `benchmarks/`. An outline or a ranked join on one of them is not an accuracy claim.

## Candidate set

### The Metropolitan Museum of Art, Open Access

- **Name.** The Metropolitan Museum of Art, Open Access images.
- **Catalogue.** [The Collection](https://www.metmuseum.org/art/collection/search). The online catalogue includes objects the museum describes as manuscripts or as parchment, including leaves and fragments when the catalogue uses those words. Select an object only when its own page shows the Open Access icon.
- **Terms.** [Terms and Conditions](https://www.metmuseum.org/policies/terms-and-conditions), last updated 25 October 2018 on that page. The same page points to [Image and Data Resources](https://www.metmuseum.org/policies/image-resources).
- **Stated license.** Materials identified by the Open Access icon are released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode). The terms say the museum makes those materials available for any purpose, including commercial and noncommercial use, free of charge and without requiring permission. CC0 requires no attribution. A courtesy citation must not imply endorsement, and it is not a trademark license. The terms reserve the museum's trademarks.
- **Commercial reuse.** Allowed for files that show the Open Access icon.
- **Local offline copy.** Allowed for those files. The terms adopt CC0, and the CC0 legal code permits copying and distribution.
- **Red lines.** A file without the Open Access icon is outside this candidate set. The terms limit those files to noncommercial, educational, and personal use, or to fair use under United States copyright law, and they prohibit commercial use. Do not redistribute them. The terms also warn that a third party may still hold rights, and they give the materials without a warranty. Catalogue geography and culture stay on the object page.

### Cleveland Museum of Art, Open Access

- **Name.** Cleveland Museum of Art, Open Access images.
- **Catalogue.** [Collection search](https://www.clevelandart.org/art/collection/search). The online catalogue includes objects the museum describes as manuscripts or as parchment, including leaves and fragments when the catalogue uses those words. Take an image only when that object's `share_license_status` is `CC0` and the object page carries the CC0 mark.
- **Terms.** [Open Access](https://www.clevelandart.org/open-access) and [Terms and Conditions](https://www.clevelandart.org/terms-and-conditions). Image-file rules for the API are on the [Open Access API](https://openaccess-api.clevelandart.org/) documentation.
- **Stated license.** CC0 images and the collection dataset are under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode). The terms say CC0 content may be copied, modified, distributed, or performed, free of charge, for commercial and noncommercial purposes, without prior permission. CC0 requires no attribution. The Open Access page gives an optional citation format and says a citation does not imply endorsement or a trademark license.
- **Commercial reuse.** Allowed when the image itself is CC0. The API documentation states that dataset text is CC0 even for copyrighted works, and that an image file is supplied only when `share_license_status` is `CC0`. Download the image only in that case.
- **Local offline copy.** Allowed for CC0 images. When a CC0 record includes an original asset, the API documentation describes that asset as a TIFF. That TIFF can be the file passed to `prw verify` when its magic matches, and to `segment` or `rank` when [ADR-0014](adr/0014-stdlib-lossless-tiff.md) accepts its layout.
- **Red lines.** `Copyrighted` and `Other` images are outside this candidate set. The terms limit content that is not marked CC0 to non-commercial, educational, and personal use, or to fair use, and they say it may not be sold without written permission. The museum disclaims third-party rights in CC0 content. A CC0 digitization, in the museum's own words, does not change the underlying copyright status of the digitized work. Catalogue text stays on the object page.

### Wikimedia Commons, file by file

- **Name.** Wikimedia Commons media files whose file page states a public-domain tag, CC0, or CC BY.
- **Entry.** [Wikimedia Commons](https://commons.wikimedia.org/). Open the file description page for each file. A category or search result is only a finding aid.
- **Terms.** [Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing) is the project policy. Reusers follow [Commons:Reusing content outside Wikimedia](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia). Attribution practice is [Commons:Credit line](https://commons.wikimedia.org/wiki/Commons:Credit_line). Photographs of flat public-domain works are discussed in [Commons:Reuse of PD-Art photographs](https://commons.wikimedia.org/wiki/Commons:Reuse_of_PD-Art_photographs).
- **Stated license.** The copyright tag on the file page is the license. Commons accepts media that are explicitly freely licensed, or that are in the public domain in the United States and in the source country. Its policy requires that republication, distribution, derivative works, and commercial use be allowed. Public-domain tags and [CC0](https://creativecommons.org/publicdomain/zero/1.0/legalcode) require no attribution. Commons asks for a courtesy credit and says public-domain attribution is recommended so the provenance stays clear. CC BY, in the version the file page names (1.0, 2.0, 2.5, 3.0, or 4.0), requires attribution. The current legal code is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode). Copy the author, the source, and the license URL from that file page into the sidecar. When a file lists more than one license, Commons allows use under any one of them. Name the license this pilot is using.
- **Commercial reuse.** Allowed for a file that meets the policy and whose tag is public domain, CC0, or CC BY. The Wikimedia Foundation does not warrant the status. The reuser verifies the file page.
- **Local offline copy.** Allowed. The licensing policy requires that distribution be allowed for media Commons accepts.
- **Red lines.** CC BY-SA, GFDL, and any non-commercial or no-derivatives tag are outside this candidate set, even if the file is on Commons. ShareAlike would bind a later derivative image, and this note sets no export license. Non-copyright restrictions, including trademarks, moral rights, and privacy, can still apply. See [Commons:Non-copyright restrictions](https://commons.wikimedia.org/wiki/Commons:Non-copyright_restrictions). Commons states that a photograph of a two-dimensional public-domain work is treated as public domain in the United States, and that some other countries restrict reuse of that photograph. Reuse of a PD-Art file outside that policy is the operator's own legal risk. The file page's description of script or origin stays on that page.

## Shared red lines

- Image bytes stay outside Git. A license that allows redistribution does not admit the file to this repository.
- Do not commit a sidecar that embeds pixels.
- Do not put these files in `benchmarks/`, and do not write a ground-truth label for them. In-repo evaluation material stays synthetic.
- Do not state a find-site, a language, or a reading from a catalogue caption. A ranked join on a later build would remain a hypothesis.
- Do not present the download as mentor TIFF data. That capture set is still unavailable.

## What stays open

[Q-SCI-15](OPEN_QUESTIONS.md#q-sci-15) is answered only for this candidate set, and only as a license posture for local storage and checksums. An accuracy claim on real manuscripts stays blocked. Synthetic tears remain the in-repository corpus. Any further source needs its own reading of that source's terms page. Operator steps for one downloaded file are [Public import path](pilot-import-path.md). One such file, checksummed and passed to `segment` and `rank`, is [First public-leaf run](pilot-first-run.md). Three Cleveland cuttings that stop in segmentation are [Cleveland 1999.137 retry](pilot-cma-1999-137.md). [Q-ENG-05](OPEN_QUESTIONS.md#q-eng-05) is closed for the TIFF library. It does not authorize a find-site, a language, or a reading.
