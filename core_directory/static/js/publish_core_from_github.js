let lastValidatedCore = null; // { blob, filename }

// --- Utility functions ---
function formatApiError(result) {
    if (typeof result === 'string') {
        return result;
    }
    if (typeof result === 'object' && result !== null) {
        let messages = [];
        // Handle top-level "message"
        if (typeof result.message === 'string') {
            messages.push(result.message);
        }
        // Handle non_field_errors
        if (Array.isArray(result.non_field_errors)) {
            messages = messages.concat(result.non_field_errors);
        }
        // Handle field-specific errors
        for (const [field, errors] of Object.entries(result)) {
            if (field === 'non_field_errors' || field === 'message') continue;
            if (Array.isArray(errors)) {
                errors.forEach(msg => {
                    messages.push(`<strong>${field}:</strong> ${msg}`);
                });
            }
        }
        if (messages.length > 0) {
            return messages.map(msg => `<div>${msg}</div>`).join('');
        }
        // Fallback: show as JSON
        return `<pre>${JSON.stringify(result, null, 2)}</pre>`;
    }
    // Fallback: show as string
    return String(result);
}

// --- Main logic ---
document.addEventListener('DOMContentLoaded', function() {

    /**
     * Extracts owner and repo from a GitHub URL.
     * @param {string} url
     * @returns {{owner: string, repo: string}|null}
     */
    function getOwnerRepo(url) {
        var match = url.match(/^https?:\/\/github\.com\/([^\/]+)\/([^\/]+?)(?:\.git)?\/?$/);
        if (!match) return null;
        return { owner: match[1], repo: match[2] };
    }

    /**
     * Renders the result area with repository and core file info, using a Bootstrap dropdown for core selection.
     * @param {object} obj
     */
    function showResult(obj) {
        const resultDiv = document.getElementById('result');
        if (obj.error) {
            resultDiv.innerHTML = `<div class="alert alert-danger">${obj.error}</div>`;
            return;
        }
        let html = '';
        if (obj.repo) {
            html += `
            <div class="card mb-3">
            ${getCardHeaderHtml("bi-github", "Repository details")}
            <div class="card-body">
                <h5 class="card-title">
                <a href="${obj.repo.url}" target="_blank"><strong>${obj.repo.name}</strong></a>
                <span class="fs-6">@${obj.parsed_version}</span>
                </h5>
                <p class="card-text">${obj.repo.description || ''}</p>
                <p class="card-text">
                <span class="me-3">⭐ ${obj.repo.stars}</span>
                <span>🍴 ${obj.repo.forks}</span>
                </p>
            </div>
            </div>
            `;
        }
        if (obj.core_files) {
            html += `
                <div class="card mb-3">
                ${getCardHeaderHtml("bi-boxes", "Select core")}
                <div class="p-3">`;
                if (obj.core_files.length > 0) {
                    const defaultCore = obj.core_files[0].core;
                    const defaultHasSig = obj.core_files[0].hasSig;
                    html += `
                        <div class="d-flex w-100 align-items-stretch gap-2 mb-3">
                            <div class="dropdown flex-grow-1">
                                <button class="btn btn-outline-primary dropdown-toggle w-100 d-flex justify-content-between align-items-center" type="button" id="coreDropdown" data-bs-toggle="dropdown" aria-expanded="false">
                                    <span id="coreDropdownLabel" class="text-truncate">${defaultCore}</span>
                                    <span class="d-flex align-items-center">
                                        ${defaultHasSig ? '<span id="coreDropdownBadge" class="badge bg-success ms-2"><i class="bi bi-shield-check"></i> signed</span>' : '<span id="coreDropdownBadge"></span>'}
                                    </span>
                                </button>
                                <ul class="dropdown-menu w-100" aria-labelledby="coreDropdown">
                                    ${obj.core_files.map(f => `
                                        <li>
                                            <a class="dropdown-item core-dropdown-item d-flex align-items-center justify-content-between" href="#" data-core="${f.core}" data-has-sig="${f.hasSig}">
                                                <span>${f.core}</span>
                                                ${f.hasSig
                                                    ? '<span class="badge bg-success ms-2"><i class="bi bi-shield-check"></i> signed</span>'
                                                    : '<span class="badge bg-danger py-1 ms-2"><i class="bi bi-shield-exclamation"></i> unsigned</span>'
                                                }
                                            </a>
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                            <button id="validate-core-btn" type="button" class="btn btn-primary">Validate</button>
                            <button id="publish-core-btn" type="button" class="btn btn-secondary" disabled>Publish</button>
                        </div>
                        <div id="validate-result" style="margin-top:1em;"></div>
                    `;
                } else {
                    html +=                    
                        `<div class="alert alert-warning">
                            <strong>No <code>.core</code> files found in the repository.</strong><br>
                            <span class="text-muted">
                                Note: Only <code>.core</code> files located in the root of the repository can be published.
                            </span>
                        </div>`;  
                }
            html += `</div></div>`;
        }
        resultDiv.innerHTML = html;

        // --- Dropdown and button event handlers ---
        let selectedCore = obj.core_files && obj.core_files[0] ? obj.core_files[0].core : null;
        let selectedHasSig = obj.core_files && obj.core_files[0] ? obj.core_files[0].hasSig : false;

        // Dropdown item click: update label, badge, and selectedCore
        document.querySelectorAll('.core-dropdown-item').forEach(item => {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                selectedCore = this.getAttribute('data-core');
                selectedHasSig = this.getAttribute('data-has-sig') === 'true';
                document.getElementById('coreDropdownLabel').textContent = selectedCore;
                // Update badge
                const badgeElem = document.getElementById('coreDropdownBadge');
                if (selectedHasSig) {
                    badgeElem.className = 'badge bg-success ms-2';
                    badgeElem.innerHTML = '<i class="bi bi-shield-check"></i> signed';
                } else {
                    badgeElem.className = '';
                    badgeElem.innerHTML = '';
                }
                // Clear validation result and disable publish when selection changes
                document.getElementById('validate-result').innerHTML = '';
                const publishBtn = document.getElementById('publish-core-btn');
                if (publishBtn) {
                    publishBtn.disabled = true;
                    publishBtn.classList.remove('btn-success');
                    publishBtn.classList.add('btn-secondary');
                }
                lastValidatedCore = null;
            });
        });

        // Validate button uses selectedCore
        const validateBtn = document.getElementById('validate-core-btn');
        if (validateBtn) {
            validateBtn.addEventListener('click', function() {
                if (selectedCore) {
                    validateCoreFile(obj, selectedCore);
                }
            });
        }

        // Publish button
        const publishBtn = document.getElementById('publish-core-btn');
        if (publishBtn) {
            publishBtn.addEventListener('click', publishCoreFile);
        }
    }

    /**
     * Returns the card header HTML with the given title.
     * @param {string} title
     * @returns {string}
     */
    function getCardHeaderHtml(icon, title) {
        let template = document.getElementById('card-header-template').innerHTML;
        return template.replace(/__TITLE__/g, title).replace(/__ICON__/g, icon);
    }

    /**
     * Clears the result display area.
     */
    function clearResult() {
        document.getElementById('result').innerHTML = '';
    }

    /**
     * Shows/hides tag and commit fields based on version type.
     */
    function toggleFields() {
        const versionType = document.getElementById('version_type').value;
        document.getElementById('tag-field').style.display = (versionType === 'tag') ? '' : 'none';
        document.getElementById('commit-field').style.display = (versionType === 'commit') ? '' : 'none';
    }

    /**
     * When the repo URL input loses focus (blur), fetch tags if "Tag" is selected.
     */
    document.getElementById('repo_url').addEventListener('blur', function() {
        if (document.getElementById('version_type').value === 'tag') {
            fetchTags();
        }
    });

    /**
     * When the version type changes, clear the result, update fields, and fetch tags if needed.
     */
    document.getElementById('version_type').addEventListener('change', function() {
        clearResult();
        toggleFields();
        if (this.value === 'tag') {
            fetchTags();
        }
    });

    /**
     * When the tag selection changes, clear the result.
     */
    document.getElementById('tag').addEventListener('change', clearResult);

    /**
     * When the commit input changes, clear the result.
     */
    document.getElementById('commit').addEventListener('input', clearResult);

    /**
     * When the repo URL input changes, clear the result.
     */
    document.getElementById('repo_url').addEventListener('input', clearResult);
    /**
     * Handles GitHub API error responses and rate limits.
     * @param {object} data
     * @param {string} defaultError
     * @param {function} [showResultFn=showResult]
     * @returns {boolean}
     */
    function handleGithubApiResponse(data, defaultError, showResultFn = showResult) {
        if (data && data.message) {
            if (data.message.includes('API rate limit exceeded')) {
                showResultFn({ error: 'GitHub API rate limit exceeded. Please wait and try again later.' });
            } else {
                showResultFn({ error: `GitHub API error: ${data.message}` });
            }
            return false;
        }
        if (data === undefined || data === null) {
            showResultFn({ error: defaultError });
            return false;
        }
        return true;
    }

    /**
     * Fetches tags for the selected repository and populates the tag select.
     */
    function fetchTags() {
        clearResult();
        const repoUrl = document.getElementById('repo_url').value;
        const info = getOwnerRepo(repoUrl);
        const tagSelect = document.getElementById('tag');
        tagSelect.innerHTML = '';
        if (!info) {
            tagSelect.innerHTML = '<option value="">Invalid URL</option>';
            return;
        }
        fetch(`https://api.github.com/repos/${info.owner}/${info.repo}/tags`)
            .then(response => response.json())
            .then(data => {
                if (!handleGithubApiResponse(data, 'Error fetching tags.')) return;
                if (Array.isArray(data) && data.length > 0) {
                    data.forEach(tag => {
                        const option = document.createElement('option');
                        option.value = tag.name;
                        option.textContent = tag.name;
                        tagSelect.appendChild(option);
                    });
                } else {
                    tagSelect.innerHTML = '<option value="">No tags found</option>';
                }
            })
            .catch(err => showResult({ error: 'Error fetching tags.' }));
    }

    /**
     * Lists all .core files in the repo root at the given SHA, and checks for signature files.
     * @param {string} owner
     * @param {string} repo
     * @param {string} sha
     * @returns {Promise<Array<{core: string, hasSig: boolean}>>}
     */
    async function listCoreFiles(owner, repo, sha) {
        const treeUrl = `https://api.github.com/repos/${owner}/${repo}/git/trees/${sha}?recursive=1`;
        try {
            const response = await fetch(treeUrl);
            const data = await response.json();
            if (!handleGithubApiResponse(data, 'Error listing .core files.')) return [];
            if (!data.tree) return [];
            // Get all file paths in the tree
            const allFiles = data.tree
                .filter(item => item.type === 'blob')
                .map(item => item.path);
            // Only root .core files
            const coreFiles = allFiles.filter(path => path.endsWith('.core') && !path.includes('/'));
            const fileSet = new Set(allFiles);
            // Map to objects with signature info
            return coreFiles.map(corePath => ({
                core: corePath,
                hasSig: fileSet.has(corePath + '.sig')
            }));
        } catch (err) {
            showResult({ error: 'Error listing .core files.' });
            return [];
        }
    }

    /**
     * Validates the selected core file by sending it to the API.
     * @param {object} obj
     * @param {string} coreFilePath
     */
    async function validateCoreFile(obj, coreFilePath) {
        const validateResultDiv = document.getElementById('validate-result');
        const publishBtn = document.getElementById('publish-core-btn');
        if (publishBtn) {
            publishBtn.disabled = true;
            publishBtn.classList.remove('btn-success');
            publishBtn.classList.add('btn-secondary');
        }
        validateResultDiv.innerHTML = 'Validating...';

        const rawUrl = `https://raw.githubusercontent.com/${obj.repo.name}/${obj.commit}/${coreFilePath}`;
        const sigUrl = rawUrl + '.sig';

        let text, sigBlob = null;
        try {
            // Fetch core file
            const response = await fetch(rawUrl);
            if (!response.ok) {
                validateResultDiv.innerHTML = '<div class="alert alert-danger">Could not fetch core file from GitHub.</div>';
                return;
            }
            text = await response.text();

            // Try to fetch signature file (optional)
            const sigResponse = await fetch(sigUrl);
            if (sigResponse.ok) {
                sigBlob = await sigResponse.blob();
            }
        } catch (err) {
            validateResultDiv.innerHTML = '<div class="alert alert-danger">Error fetching core or signature file.</div>';
            return;
        }

        let coreObj;
        try {
            coreObj = jsyaml.load(text);
        } catch (e) {
            validateResultDiv.innerHTML = `<div class="alert alert-danger">Could not parse YAML: ${e}</div>`;
            return;
        }

        if (coreObj && typeof coreObj === 'object' && 'provider' in coreObj) {
            validateResultDiv.innerHTML =
                `<div class="alert alert-warning">
                    This .core file refers to an external <code>provider</code> and therefore cannot be uploaded via web interface.<br>
                    <strong>Reason:</strong> Only core files <b>without</b> a provider section are accepted. The .core file and its source files need to be located in the same repository.
                    <strong>Hint:</strong> To publish core files referring to a github in its provider section, please use the API directly.
                </div>`;
            return;
        }

        // Add provider section
        const [owner, repo] = obj.repo.name.split('/');
        coreObj.provider = {
            name: "github",
            user: owner,
            repo: repo,
            version: obj.commit
        };

        const newYaml = jsyaml.dump(coreObj);
        const blob = new Blob([newYaml], { type: "application/x-yaml" });

        const formData = new FormData();
        formData.append('core_file', blob, coreFilePath);
        if (sigBlob) {
            formData.append('signature_file', sigBlob, coreFilePath + '.sig');
        }

        let validateResponse, respText, result;
        try {
            validateResponse = await fetch('/api/v1/validate/', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });
            respText = await validateResponse.text();
            try {
                result = JSON.parse(respText);
            } catch {
                result = respText;
            }
        } catch (err) {
            validateResultDiv.innerHTML = '<div class="alert alert-danger"><strong>Error during validation.</strong></div>';
            return;
        }

        if (validateResponse.ok) {
            lastValidatedCore = { blob, filename: coreFilePath, sigBlob };
            validateResultDiv.innerHTML =
                `<div class="alert alert-success">
                    Validation successful!<br>
                </div>`;
            if (publishBtn) {
                publishBtn.disabled = false;
                publishBtn.classList.remove('btn-secondary');
                publishBtn.classList.add('btn-success');
            }
        } else {
            lastValidatedCore = null;
            validateResultDiv.innerHTML =
                `<div class="alert alert-danger"><strong>Validation failed!</strong><br>${formatApiError(result)}</div>`;
        }
    }

    /**
     * Publishes the last validated core file to the API.
     */
    async function publishCoreFile() {
        if (!lastValidatedCore) return;
        const publishBtn = document.getElementById('publish-core-btn');
        if (publishBtn) {
            publishBtn.disabled = true;
            publishBtn.classList.remove('btn-success');
            publishBtn.classList.add('btn-secondary');
        }
        document.getElementById('validate-result').innerHTML = 'Publishing...';

        const formData = new FormData();
        formData.append('core_file', lastValidatedCore.blob, lastValidatedCore.filename);
        if (lastValidatedCore.sigBlob) {
            formData.append('signature_file', lastValidatedCore.sigBlob, lastValidatedCore.filename + '.sig');
        }

        try {
            const publishResponse = await fetch('/api/v1/publish/', {
                method: 'POST',
                body: formData,
                credentials: 'same-origin',
            });

            const respText = await publishResponse.text();
            let result;
            try {
                result = JSON.parse(respText);
            } catch {
                result = respText;
            }

            if (publishResponse.ok) {
                document.getElementById('validate-result').innerHTML =
                    `<div class="alert alert-success"><strong>Published successful!</strong></div>`;
            } else {
                document.getElementById('validate-result').innerHTML =
                    `<div class="alert alert-danger"><strong>Publishing failed!</strong><br>${formatApiError(result)}</div>`;
            }
        } catch (err) {
            document.getElementById('validate-result').innerHTML =
                `<div class="alert alert-danger"><strong>Error during publish.</strong></div>`;
        }
    }

    // --- Main Form Submission ---

    document.getElementById('repo-form').addEventListener('submit', function(e) {
        e.preventDefault();
        clearResult();

        const repoUrl = document.getElementById('repo_url').value;
        const versionType = document.getElementById('version_type').value;
        const info = getOwnerRepo(repoUrl);

        if (!info) {
            showResult({ error: 'Invalid GitHub URL.' });
            return;
        }

        fetch(`https://api.github.com/repos/${info.owner}/${info.repo}`)
            .then(response => response.json())
            .then(repoData => {
                if (!handleGithubApiResponse(repoData, 'Repository not found.')) return;

                function processSha(sha, extra) {
                    let versionStr = ``;
                    if (versionType === 'tag') {
                        versionStr += `${document.getElementById('tag').value}`;
                    } else if (versionType === 'commit') {
                        versionStr += `${document.getElementById('commit').value}`;
                    } else {
                        versionStr += 'latest';
                    }
                    listCoreFiles(info.owner, info.repo, sha)
                        .then(coreFiles => {
                            showResult({
                                repo: {
                                    name: repoData.full_name,
                                    description: repoData.description,
                                    stars: repoData.stargazers_count,
                                    forks: repoData.forks_count,
                                    url: repoData.html_url,
                                },
                                parsed_version: versionStr,
                                ...extra,
                                core_files: coreFiles,
                            });
                        })
                        .catch(err => showResult({ error: 'Error listing .core files.' }));
                }

                if (versionType === 'latest') {
                    fetch(`https://api.github.com/repos/${info.owner}/${info.repo}/commits`)
                        .then(response => response.json())
                        .then(data => {
                            if (!handleGithubApiResponse(data, 'Error fetching latest commit.')) return;
                            if (Array.isArray(data) && data.length > 0) {
                                processSha(data[0].sha, {
                                    type: 'latest',
                                    commit: data[0].sha,
                                    message: data[0].commit.message,
                                });
                            } else {
                                showResult({ error: 'No commits found.' });
                            }
                        })
                        .catch(err => showResult({ error: 'Error fetching latest commit.' }));

                } else if (versionType === 'tag') {
                    const tag = document.getElementById('tag').value;
                    if (!tag) {
                        showResult({ error: 'No tag selected.' });
                        return;
                    }
                    fetch(`https://api.github.com/repos/${info.owner}/${info.repo}/tags`)
                        .then(response => response.json())
                        .then(data => {
                            if (!handleGithubApiResponse(data, 'Error fetching tags.')) return;
                            const tagObj = Array.isArray(data) ? data.find(t => t.name === tag) : null;
                            if (tagObj) {
                                processSha(tagObj.commit.sha, {
                                    type: 'tag',
                                    tag: tag,
                                    commit: tagObj.commit.sha,
                                });
                            } else {
                                showResult({ error: 'Tag not found.' });
                            }
                        })
                        .catch(err => showResult({ error: 'Error fetching tag info.' }));

                } else if (versionType === 'commit') {
                    const commit = document.getElementById('commit').value;
                    if (!commit) {
                        showResult({ error: 'Please enter a commit hash.' });
                        return;
                    }
                    fetch(`https://api.github.com/repos/${info.owner}/${info.repo}/commits/${commit}`)
                        .then(response => response.json())
                        .then(data => {
                            if (!handleGithubApiResponse(data, 'Error fetching commit info.')) return;
                            if (data && data.sha) {
                                processSha(data.sha, {
                                    type: 'commit',
                                    commit: data.sha,
                                    message: data.commit.message,
                                });
                            } else {
                                showResult({ error: 'Commit not found.' });
                            }
                        })
                        .catch(err => showResult({ error: 'Error fetching commit info.' }));
                }
            })
            .catch(err => showResult({ error: 'Error fetching repository details.' }));
        toggleFields();
    });

    toggleFields();
});