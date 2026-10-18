/**
 * Batch Processor
 * Efficient batch processing for multi-track operations
 */

interface BatchProgress {
  total: number;
  processed: number;
  failed: number;
  percentComplete: number;
}

interface BatchResult<T> {
  success: T[];
  failed: Array<{ id: string; error: string }>;
  progress: BatchProgress;
}

/**
 * Process items in batches to control memory usage
 */
export async function processBatch<T, R>(
  items: T[],
  processor: (item: T) => Promise<R>,
  batchSize: number = 10,
  onProgress?: (progress: BatchProgress) => void
): Promise<BatchResult<R>> {
  const result: BatchResult<R> = {
    success: [],
    failed: [],
    progress: {
      total: items.length,
      processed: 0,
      failed: 0,
      percentComplete: 0,
    },
  };

  // Process in batches
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);

    // Process batch in parallel
    const batchResults = await Promise.allSettled(
      batch.map((item) => processor(item))
    );

    // Handle results
    batchResults.forEach((batchResult, index) => {
      result.progress.processed++;

      if (batchResult.status === 'fulfilled') {
        result.success.push(batchResult.value);
      } else {
        result.progress.failed++;
        result.failed.push({
          id: `item_${i + index}`,
          error: batchResult.reason?.message || 'Unknown error',
        });
      }

      // Update progress
      result.progress.percentComplete = Math.round(
        (result.progress.processed / result.progress.total) * 100
      );

      if (onProgress) {
        onProgress(result.progress);
      }
    });

    // Allow garbage collection between batches
    await new Promise(resolve => setImmediate(resolve));
  }

  return result;
}

/**
 * Stream process items to avoid loading all into memory
 */
export async function streamBatch<T, R>(
  items: T[],
  processor: (item: T) => Promise<R>,
  batchSize: number = 10,
  onItem?: (item: R, index: number) => void,
  onProgress?: (progress: BatchProgress) => void
): Promise<BatchResult<R>> {
  const result: BatchResult<R> = {
    success: [],
    failed: [],
    progress: {
      total: items.length,
      processed: 0,
      failed: 0,
      percentComplete: 0,
    },
  };

  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);

    const batchResults = await Promise.allSettled(
      batch.map((item, index) => processor(item))
    );

    batchResults.forEach((batchResult, index) => {
      result.progress.processed++;

      if (batchResult.status === 'fulfilled') {
        result.success.push(batchResult.value);
        if (onItem) {
          onItem(batchResult.value, result.success.length - 1);
        }
      } else {
        result.progress.failed++;
        result.failed.push({
          id: `item_${i + index}`,
          error: batchResult.reason?.message || 'Unknown error',
        });
      }

      result.progress.percentComplete = Math.round(
        (result.progress.processed / result.progress.total) * 100
      );

      if (onProgress) {
        onProgress(result.progress);
      }
    });

    // Allow garbage collection
    await new Promise(resolve => setImmediate(resolve));
  }

  return result;
}

/**
 * Check if batch operation would exceed memory limits
 */
export function validateBatchSize(
  itemCount: number,
  estimatedSizePerItem: number, // in bytes
  maxMemoryMB: number = 500
): { valid: boolean; recommendedBatchSize: number } {
  const maxBytes = maxMemoryMB * 1024 * 1024;
  const totalEstimated = itemCount * estimatedSizePerItem;

  if (totalEstimated <= maxBytes) {
    return { valid: true, recommendedBatchSize: itemCount };
  }

  const recommendedBatchSize = Math.floor(maxBytes / estimatedSizePerItem);
  return {
    valid: recommendedBatchSize > 0,
    recommendedBatchSize: Math.max(1, recommendedBatchSize),
  };
}

/**
 * Chunked array helper
 */
export function* chunkArray<T>(array: T[], size: number): Generator<T[]> {
  for (let i = 0; i < array.length; i += size) {
    yield array.slice(i, i + size);
  }
}
