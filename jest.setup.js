import '@testing-library/jest-dom'

// Make fetch available globally for Node 16 compatibility
if (!global.fetch) {
  global.fetch = require('node-fetch')
}
