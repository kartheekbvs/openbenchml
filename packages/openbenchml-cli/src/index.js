/**
 * Public entrypoint — re-export the API client for programmatic use.
 *
 * Example:
 *   const { ApiClient } = require('openbenchml-cli');
 *   const client = new ApiClient({ host: 'http://localhost:8000' });
 *   await client.login('me@example.com', 'pwd');
 *   await client.uploadModel({ filePath: './rf.joblib', name: 'RF', framework: 'scikit-learn' });
 */

module.exports = {
  ApiClient: require('./client').ApiClient,
  Command: require('./command').Command,
};
