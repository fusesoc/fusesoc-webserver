let lastValidatedCore = null; // { blob, filename }

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
     * Renders the result area with repository and core file info.
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
                <a href="${obj.repo.url}" target="_blank">${obj.repo.name}</a>
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
            html += `${getCardHeaderHtml("bi-boxes", "Available cores")}`;
            if (obj.core_files.length > 0) {
                html += `
                    <div class="input-group mb-3">
                        <select id="core-file-select" class="form-select">
                            ${obj.core_files.map(f => `<option value="${f}">${f}</option>`).join('')}
                        </select>
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
        }
        // html += `<pre>${JSON.stringify(obj, null, 2)}</pre>`;
        resultDiv.innerHTML = html;

        // Add event listeners
        const validateBtn = document.getElementById('validate-core-btn');
        const publishBtn = document.getElementById('publish-core-btn');
        const select = document.getElementById('core-file-select');

        if (validateBtn) {
            validateBtn.addEventListener('click', function() {
                const coreFilePath = select.value;
                validateCoreFile(obj, coreFilePath);
            });
        }
        if (publishBtn) {
            publishBtn.addEventListener('click', publishCoreFile);
        }
        if (select) {
            select.addEventListener('change', function() {
                // Clear validation result and disable publish when selection changes
                document.getElementById('validate-result').innerHTML = '';
                if (publishBtn) {
                    publishBtn.disabled = true;
                    publishBtn.classList.remove('btn-success');
                    publishBtn.classList.add('btn-secondary');
                }
                lastValidatedCore = null;
            });
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
     * Lists all .core files in the repo at the given SHA.
     * @param {string} owner
     * @param {string} repo
     * @param {string} sha
     * @returns {Promise<string[]>}
     */
    async function listCoreFiles(owner, repo, sha) {
        const treeUrl = `https://api.github.com/repos/${owner}/${repo}/git/trees/${sha}?recursive=1`;
        try {
            const response = await fetch(treeUrl);
            const data = await response.json();
            if (!handleGithubApiResponse(data, 'Error listing .core files.')) return [];
            if (!data.tree) return [];
            return data.tree
                .filter(item => 
                    item.type === 'blob' && 
                    item.path.endsWith('.core') &&
                    !item.path.includes('/') // Only root files                
                )
                .map(item => item.path);
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

        let text;
        try {
            const response = await fetch(rawUrl);
            if (!response.ok) {
                if (response.status === 403) {
                    let errMsg = 'Could not fetch core file from GitHub (403 Forbidden).';
                    try {
                        const errData = await response.json();
                        if (errData && errData.message && errData.message.includes('API rate limit exceeded')) {
                            errMsg = 'GitHub API rate limit exceeded. Please wait and try again later.';
                        } else if (errData && errData.message) {
                            errMsg = `GitHub API error: ${errData.message}`;
                        }
                    } catch {}
                    validateResultDiv.innerHTML = `<div class="alert alert-danger">${errMsg}</div>`;
                    return;
                }
                validateResultDiv.innerHTML = '<div class="alert alert-danger">Could not fetch core file from GitHub.</div>';
                return;
            }
            text = await response.text();
        } catch (err) {
            validateResultDiv.innerHTML = '<div class="alert alert-danger">Error fetching core file.</div>';
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
                    This .core file reffers to an external <code>provider</code> and therefore can not be uploaded via web interface<br>
                    <strong>Reason:</strong> Only core files <b>without</b> a provider section are accepted. The .core file and its source files need to be located in the same repository.
                    <strong>Hint:</strong> To publish core files reffering to a github in its provider section, please use the API directly.
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
            validateResultDiv.innerHTML = '<div class="alert alert-danger">Error during validation.</div>';
            return;
        }

        if (validateResponse.ok) {
            lastValidatedCore = { blob, filename: coreFilePath };
            validateResultDiv.innerHTML =
                `<div class="alert alert-success">
                    Validation successful!<br>
                    <pre>${JSON.stringify(result, null, 2)}</pre>
                </div>`;
            if (publishBtn) {
                publishBtn.disabled = false;
                publishBtn.classList.remove('btn-secondary');
                publishBtn.classList.add('btn-success');
            }
        } else {
            lastValidatedCore = null;
            let errorMsg = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
            validateResultDiv.innerHTML =
                `<div class="alert alert-danger">Validation failed:<br><pre>${errorMsg}</pre></div>`;
            if (publishBtn) {
                publishBtn.disabled = true;
                publishBtn.classList.remove('btn-success');
                publishBtn.classList.add('btn-secondary');
            }
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
                    `<div class="alert alert-success">Publish successful!<br><pre>${JSON.stringify(result, null, 2)}</pre></div>`;
            } else {
                document.getElementById('validate-result').innerHTML =
                    `<div class="alert alert-danger">Publish failed:<br><pre>${JSON.stringify(result, null, 2)}</pre></div>`;
            }
        } catch (err) {
            document.getElementById('validate-result').innerHTML = 'Error during publish.';
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