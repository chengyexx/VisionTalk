/**
 * RingBuffer — fixed-capacity circular buffer.
 * When full, the oldest item is overwritten (FIFO with eviction).
 */
export class RingBuffer<T> {
  private buffer: T[];
  private capacity: number;
  private head: number = 0;
  private count: number = 0;

  constructor(capacity: number = 30) {
    this.capacity = capacity;
    this.buffer = new Array<T>(capacity);
  }

  /** Add an item. If full, overwrites the oldest entry. */
  push(item: T): void {
    const index = (this.head + this.count) % this.capacity;
    this.buffer[index] = item;
    if (this.count < this.capacity) {
      this.count++;
    } else {
      this.head = (this.head + 1) % this.capacity;
    }
  }

  /** Get the most recently added item, or null if empty. */
  getLatest(): T | null {
    if (this.count === 0) return null;
    const index = (this.head + this.count - 1) % this.capacity;
    return this.buffer[index];
  }

  /** Get a snapshot of all items in insertion order (oldest first). */
  getAll(): T[] {
    const result: T[] = [];
    for (let i = 0; i < this.count; i++) {
      result.push(this.buffer[(this.head + i) % this.capacity]);
    }
    return result;
  }

  /** Current number of items in the buffer. */
  get size(): number {
    return this.count;
  }

  /** Remove all items. */
  clear(): void {
    this.head = 0;
    this.count = 0;
  }
}
