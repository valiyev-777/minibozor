/**
 * The courier's own copy of the day, in IndexedDB.
 *
 * Two stores and no ORM. `localStorage` was not an option for the queue: it is
 * synchronous, it is capped around five megabytes, and — the part that decides
 * it — it has no transactions, so "write the row, then mark it sent" has a gap
 * in the middle that a killed tab lands in. A delivery that fell into that gap
 * would either be lost or be sent twice.
 *
 * `outbox`  — writes the courier has made that the server has not accepted.
 * `cache`   — the last thing the server said, so the app opens in a basement.
 *
 * The database is opened once and the handle reused: every screen reads from
 * it on mount, and opening per call turned into a noticeable stutter on the
 * kind of phone this runs on.
 */

const NAME = "minibozor-courier"
const VERSION = 1

export const OUTBOX = "outbox"
export const CACHE = "cache"

let handle: Promise<IDBDatabase> | null = null

export function db(): Promise<IDBDatabase> {
  if (!handle) {
    handle = new Promise((resolve, reject) => {
      const request = indexedDB.open(NAME, VERSION)
      request.onupgradeneeded = () => {
        const database = request.result
        if (!database.objectStoreNames.contains(OUTBOX)) {
          database.createObjectStore(OUTBOX, { keyPath: "id", autoIncrement: true })
        }
        if (!database.objectStoreNames.contains(CACHE)) {
          database.createObjectStore(CACHE, { keyPath: "key" })
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
  }
  return handle
}

/**
 * Close the connection and forget it.
 *
 * Used by the tests to stand in for the phone being restarted — the next call
 * to [db] opens the database again from disk, which is exactly what a reload
 * does. Closing rather than only dropping the reference: an open connection
 * blocks `deleteDatabase`, and a test that quietly waited on that was a test
 * that timed out rather than failed.
 */
export function resetDbHandle(): void {
  const closing = handle
  handle = null
  void closing?.then((database) => database.close()).catch(() => {})
}

function run<T>(store: IDBObjectStore, request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    store.transaction.onabort = () => reject(store.transaction.error)
  })
}

export async function put<T>(storeName: string, value: T): Promise<IDBValidKey> {
  const database = await db()
  const tx = database.transaction(storeName, "readwrite")
  const store = tx.objectStore(storeName)
  return run(store, store.put(value as never))
}

export async function add<T>(storeName: string, value: T): Promise<IDBValidKey> {
  const database = await db()
  const tx = database.transaction(storeName, "readwrite")
  const store = tx.objectStore(storeName)
  return run(store, store.add(value as never))
}

export async function get<T>(storeName: string, key: IDBValidKey): Promise<T | undefined> {
  const database = await db()
  const tx = database.transaction(storeName, "readonly")
  const store = tx.objectStore(storeName)
  return run<T | undefined>(store, store.get(key) as IDBRequest<T | undefined>)
}

/**
 * Everything in the store, in key order.
 *
 * Key order is insertion order for the outbox — its key auto-increments — and
 * that is not incidental: the queue is sent oldest first, and "oldest" is
 * defined by this ordering rather than by a timestamp a phone with a wrong
 * clock could scramble.
 */
export async function all<T>(storeName: string): Promise<T[]> {
  const database = await db()
  const tx = database.transaction(storeName, "readonly")
  const store = tx.objectStore(storeName)
  return run<T[]>(store, store.getAll() as IDBRequest<T[]>)
}

export async function remove(storeName: string, key: IDBValidKey): Promise<void> {
  const database = await db()
  const tx = database.transaction(storeName, "readwrite")
  const store = tx.objectStore(storeName)
  await run(store, store.delete(key))
}

export async function clearStore(storeName: string): Promise<void> {
  const database = await db()
  const tx = database.transaction(storeName, "readwrite")
  const store = tx.objectStore(storeName)
  await run(store, store.clear())
}

/**
 * Ask the browser not to evict this origin's storage.
 *
 * Chrome clears "best effort" storage when the device runs short of space, and
 * a courier's issued phone is always short of space. What would be evicted is
 * the queue: deliveries the courier has already made and has no way to make
 * again. Granted without a prompt once the app is installed to the home
 * screen, which is how it is meant to be used and what the README tells
 * dispatch to set up.
 */
export async function askForPersistence(): Promise<boolean> {
  if (!navigator.storage?.persist) return false
  try {
    if (await navigator.storage.persisted()) return true
    return await navigator.storage.persist()
  } catch {
    return false
  }
}
