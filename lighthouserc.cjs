module.exports = {
  ci: {
    collect: {
      url: ['http://127.0.0.1:8000/'],
      numberOfRuns: 1,
      settings: {
        chromeFlags: '--headless --no-sandbox --disable-dev-shm-usage',
        onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
      },
    },
    assert: {
      assertions: {
        'categories:accessibility': ['error', { minScore: 0.9 }],
        'categories:best-practices': ['error', { minScore: 0.9 }],
        'categories:performance': ['warn', { minScore: 0.9 }],
        'categories:seo': ['warn', { minScore: 0.85 }],
      },
    },
    upload: {
      target: 'filesystem',
      outputDir: '.lighthouseci',
    },
  },
};
