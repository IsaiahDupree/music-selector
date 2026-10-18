/**
 * Search Cache
 * In-memory cache for search results to improve performance
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number; // Time to live in milliseconds
}

class SearchCache {
  private cache: Map<string, CacheEntry<any>> = new Map();
  private readonly defaultTTL = 5 * 60 * 1000; // 5 minutes default
  private cleanupInterval: NodeJS.Timeout | null = null;

  constructor() {
    // Start cleanup interval to remove expired entries
    if (typeof globalThis !== 'undefined') {
      this.cleanupInterval = setInterval(() => this.cleanup(), 60000); // Every minute
    }
  }

  /**
   * Get value from cache if not expired
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    // Check if expired
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.data as T;
  }

  /**
   * Set value in cache with optional TTL
   */
  set<T>(key: string, value: T, ttl?: number): void {
    this.cache.set(key, {
      data: value,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTTL,
    });
  }

  /**
   * Clear specific cache entry
   */
  invalidate(key: string): void {
    this.cache.delete(key);
  }

  /**
   * Clear all cache entries matching pattern
   */
  invalidatePattern(pattern: RegExp): void {
    const keys = Array.from(this.cache.keys());
    keys.forEach(key => {
      if (pattern.test(key)) {
        this.cache.delete(key);
      }
    });
  }

  /**
   * Clear all cache
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get cache hit rate
   */
  getStats(): { size: number; memoryUsage: number } {
    let memoryUsage = 0;
    this.cache.forEach(entry => {
      // Rough estimate of memory usage
      memoryUsage += JSON.stringify(entry.data).length;
    });

    return {
      size: this.cache.size,
      memoryUsage,
    };
  }

  /**
   * Remove expired entries
   */
  private cleanup(): void {
    const now = Date.now();
    const keysToDelete: string[] = [];

    this.cache.forEach((entry, key) => {
      if (now - entry.timestamp > entry.ttl) {
        keysToDelete.push(key);
      }
    });

    keysToDelete.forEach(key => this.cache.delete(key));
  }

  /**
   * Destroy cleanup interval
   */
  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
    this.cache.clear();
  }
}

// Singleton instance
let cacheInstance: SearchCache | null = null;

export function getSearchCache(): SearchCache {
  if (!cacheInstance) {
    cacheInstance = new SearchCache();
  }
  return cacheInstance;
}

/**
 * Generate cache key for search query
 */
export function generateSearchCacheKey(
  query: string,
  filters?: Record<string, any>
): string {
  const filterStr = filters ? JSON.stringify(filters) : '';
  return `search:${query}:${filterStr}`;
}

/**
 * Cache wrapper for search operations
 */
export async function getCachedSearch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl?: number
): Promise<T> {
  const cache = getSearchCache();

  // Try to get from cache
  const cached = cache.get<T>(key);
  if (cached !== null) {
    return cached;
  }

  // Fetch and cache result
  const result = await fetcher();
  cache.set(key, result, ttl);
  return result;
}
