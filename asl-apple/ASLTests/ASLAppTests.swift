// ASLAppTests.swift
// ASLTests
//
// App-layer unit tests (the engine's golden-vector suite lives in
// PacingKit/Tests). These cover the seams that don't need a network or a
// camera: deep-link parsing, share-extension handoff, and wire decoding.

import XCTest
@testable import ASL

final class DeepLinkTests: XCTestCase {

    func testParsesScanWithURL() throws {
        let encoded = "https%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3Dabc123"
        let link = DeepLink.parse(try XCTUnwrap(URL(string: "asl://scan?url=\(encoded)")))
        XCTAssertEqual(
            link,
            .scan(videoURL: URL(string: "https://youtube.com/watch?v=abc123"))
        )
    }

    func testParsesBareScan() throws {
        let link = DeepLink.parse(try XCTUnwrap(URL(string: "asl://scan")))
        XCTAssertEqual(link, .scan(videoURL: nil))
    }

    func testRejectsForeignScheme() throws {
        XCTAssertNil(DeepLink.parse(try XCTUnwrap(URL(string: "https://scan?url=x"))))
    }

    func testRejectsUnknownHost() throws {
        XCTAssertNil(DeepLink.parse(try XCTUnwrap(URL(string: "asl://settings"))))
    }
}

final class PendingScanStoreTests: XCTestCase {

    /// Plain suite (not an app group) so the test runs without entitlements.
    private let suite = "ASLTests.pendingScan"

    override func tearDown() {
        UserDefaults(suiteName: suite)?.removePersistentDomain(forName: suite)
        super.tearDown()
    }

    func testSaveThenConsumeRoundTripsAndClears() throws {
        let store = PendingScanStore(suiteName: suite)
        let url = try XCTUnwrap(URL(string: "https://youtube.com/watch?v=abc"))

        store.save(url)
        XCTAssertEqual(store.consume(), url)
        XCTAssertNil(store.consume(), "consume() must clear the slot")
    }

    func testLastWriteWins() throws {
        let store = PendingScanStore(suiteName: suite)
        store.save(try XCTUnwrap(URL(string: "https://example.com/first")))
        store.save(try XCTUnwrap(URL(string: "https://example.com/second")))
        XCTAssertEqual(store.consume()?.absoluteString, "https://example.com/second")
    }
}

final class ModelDecodingTests: XCTestCase {

    private func makeDecoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    func testDecodesLeaderboardItem() throws {
        let json = """
        {
          "rank": 1,
          "channel_id": "ch_123",
          "title": "Example Channel",
          "category": "animation",
          "subscriber_count": 1200000,
          "score": 87.5,
          "trend": "speeding_up",
          "n_videos": 24
        }
        """
        let item = try makeDecoder().decode(LeaderboardItem.self, from: Data(json.utf8))
        XCTAssertEqual(item.channelId, "ch_123")
        XCTAssertEqual(item.trend, .speedingUp)
        XCTAssertEqual(item.score, 87.5, accuracy: 1e-12)
    }

    func testDecodesAnalysisWithNullsWhileQueued() throws {
        let json = """
        {
          "id": "an_1",
          "status": "queued",
          "engine_version": "1.0.0",
          "score": null,
          "label": null,
          "median_shot_s": null,
          "cuts_per_minute": null,
          "cut_count": null,
          "duration_s": null,
          "heatmap_png_url": null,
          "result_json_url": null,
          "source": "url",
          "share_slug": null,
          "created_at": "2026-07-16T12:00:00Z",
          "completed_at": null
        }
        """
        let analysis = try makeDecoder().decode(Analysis.self, from: Data(json.utf8))
        XCTAssertEqual(analysis.status, .queued)
        XCTAssertNil(analysis.score)
        XCTAssertFalse(analysis.isTerminal)
    }
}
