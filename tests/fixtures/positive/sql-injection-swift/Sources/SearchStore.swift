import GRDB

struct SearchStore {
    let dbQueue: DatabaseQueue

    // term đến từ deep link myapp://search?q=... (L1)
    func search(term: String) throws -> [Row] {
        try dbQueue.read { db in
            try Row.fetchAll(db, sql: "SELECT * FROM item WHERE title = '\(term)'")
        }
    }
}
