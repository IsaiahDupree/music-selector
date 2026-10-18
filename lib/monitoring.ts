/**
 * Application monitoring utilities
 */

interface ErrorLog {
  timestamp: string;
  error: string;
  stack?: string;
  context?: Record<string, any>;
}

interface PerformanceMetric {
  name: string;
  duration: number;
  timestamp: string;
}

const errorLogs: ErrorLog[] = [];
const performanceMetrics: PerformanceMetric[] = [];

/**
 * Log an error for monitoring
 */
export function logError(
  error: Error | string,
  context?: Record<string, any>
) {
  const errorLog: ErrorLog = {
    timestamp: new Date().toISOString(),
    error: error instanceof Error ? error.message : error,
    stack: error instanceof Error ? error.stack : undefined,
    context,
  };

  errorLogs.push(errorLog);

  // Keep only recent errors (last 100)
  if (errorLogs.length > 100) {
    errorLogs.shift();
  }

  // Log to console in development
  if (process.env.NODE_ENV === "development") {
    console.error("[ERROR LOG]", errorLog);
  }
}

/**
 * Record a performance metric
 */
export function recordMetric(name: string, duration: number) {
  const metric: PerformanceMetric = {
    name,
    duration,
    timestamp: new Date().toISOString(),
  };

  performanceMetrics.push(metric);

  // Keep only recent metrics (last 100)
  if (performanceMetrics.length > 100) {
    performanceMetrics.shift();
  }
}

/**
 * Get error logs
 */
export function getErrorLogs(limit: number = 10) {
  return errorLogs.slice(-limit).reverse();
}

/**
 * Get performance metrics
 */
export function getMetrics(limit: number = 10) {
  return performanceMetrics.slice(-limit).reverse();
}

/**
 * Get aggregated metrics
 */
export function getMetricsStats() {
  const recent = performanceMetrics.slice(-100);

  if (recent.length === 0) {
    return {
      totalRequests: 0,
      averageResponseTime: 0,
      slowRequests: [],
    };
  }

  const durations = recent.map(m => m.duration);
  const averageResponseTime =
    durations.reduce((a, b) => a + b, 0) / durations.length;
  const slowRequests = recent
    .filter(m => m.duration > averageResponseTime * 2)
    .slice(-5);

  return {
    totalRequests: recent.length,
    averageResponseTime: Math.round(averageResponseTime),
    slowRequests,
  };
}

/**
 * Clear all logs (for testing/reset)
 */
export function clearLogs() {
  errorLogs.length = 0;
  performanceMetrics.length = 0;
}
