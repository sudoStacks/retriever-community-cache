Contribution Guidelines

Contributions are welcome.

Requirements:
	•	Valid MusicBrainz recording MBID
	•	Public YouTube video identifier
	•	Confidence at or above the repository publish floor in `.github/publish_policy.json`
	•	Transport mapping data only (do not submit MusicBrainz metadata copies)

Preferred sources:
	•	Official artist uploads
	•	Label uploads
	•	Deterministically verified Retreivr matches

Avoid:
	•	Unofficial uploads when better verified sources exist
	•	Private videos
	•	Geo-blocked or unstable media
	•	Manual edits that bypass schema or CI policy

Preferred automated flow:
	•	Retreivr writes dataset updates to a trusted branch
	•	A same-repo PR is opened
	•	CI validates schema and policy gates
	•	Trusted PR auto-merge handles publication to `main`

Trusted publisher access:
	•	Open a GitHub Issue titled `Trusted Publisher Request: <your-github-username>`
	•	Describe how you run Retreivr and where your publish proposals come from
	•	Include links to prior good PRs if available
	•	Maintainers approve by adding your GitHub username to `.github/trusted_publishers.txt`

Until approved:
	•	You may still submit proposals or open PRs
	•	Auto-merge is reserved for trusted publishers only
