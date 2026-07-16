// GoldenVectorTests.swift
// PacingKitTests
//
// Engine-parity contract: every vector in fixtures/golden_vectors.json (shared
// with the backend's pytest suite) must pass here at the same engine version.
// Numeric assertions use 1e-9 absolute tolerance, per the fixture's own notes.

import XCTest
@testable import PacingKit

final class GoldenVectorTests: XCTestCase {

    // MARK: - Fixture schema

    private struct Fixture: Decodable {
        let engineVersion: String
        let pacingScore: [ScoreVector]
        let heatmap: [HeatmapVector]
        let summarize: [SummarizeVector]
    }

    private struct ScoreVector: Decodable {
        let medianShotS: Double
        let score: Double
        let label: String
    }

    private struct HeatmapVector: Decodable {
        let name: String
        let cutTimes: [Double]
        let durationS: Double
        let binS: Double
        let windowS: Double
        let binCentersS: [Double]
        let cutsPerMin: [Double]
    }

    private struct SummarizeVector: Decodable {
        let name: String
        let cutTimes: [Double]
        let durationS: Double
        let expected: ExpectedSummary
    }

    private struct ExpectedSummary: Decodable {
        let engineVersion: String
        let durationS: Double
        let cutCount: Int
        let medianShotS: Double
        let cutsPerMinute: Double
        let score: Double
        let label: String
        let heatmap: ExpectedHeatmap
    }

    private struct ExpectedHeatmap: Decodable {
        let binCentersS: [Double]
        let cutsPerMin: [Double]
    }

    private static let tolerance = 1e-9

    private func loadFixture() throws -> Fixture {
        let url = try XCTUnwrap(
            Bundle.module.url(
                forResource: "golden_vectors",
                withExtension: "json",
                subdirectory: "Fixtures"
            ),
            "golden_vectors.json missing from test bundle"
        )
        let data = try Data(contentsOf: url)
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Fixture.self, from: data)
    }

    // MARK: - Tests

    func testEngineVersionMatchesFixture() throws {
        let fixture = try loadFixture()
        XCTAssertEqual(
            PacingEngine.engineVersion, fixture.engineVersion,
            "Engine version drift: bump both sides together or scores stop being comparable"
        )
    }

    func testPacingScoreVectors() throws {
        let fixture = try loadFixture()
        XCTAssertFalse(fixture.pacingScore.isEmpty)
        for vector in fixture.pacingScore {
            let score = PacingEngine.pacingScore(medianShotLength: vector.medianShotS)
            XCTAssertEqual(
                score, vector.score, accuracy: Self.tolerance,
                "pacingScore(\(vector.medianShotS))"
            )
            XCTAssertEqual(
                PacingEngine.label(forScore: score).rawValue, vector.label,
                "label for median \(vector.medianShotS)s"
            )
        }
    }

    func testHeatmapVectors() throws {
        let fixture = try loadFixture()
        XCTAssertFalse(fixture.heatmap.isEmpty)
        for vector in fixture.heatmap {
            let result = PacingEngine.buildHeatmap(
                cutTimes: vector.cutTimes,
                duration: vector.durationS,
                binS: vector.binS,
                windowS: vector.windowS
            )
            assertEqual(result.binCenters, vector.binCentersS, label: "\(vector.name) bin centers")
            assertEqual(result.cutsPerMin, vector.cutsPerMin, label: "\(vector.name) cuts/min")
        }
    }

    func testSummarizeVectors() throws {
        let fixture = try loadFixture()
        XCTAssertFalse(fixture.summarize.isEmpty)
        for vector in fixture.summarize {
            let summary = PacingEngine.summarize(
                cutTimes: vector.cutTimes,
                duration: vector.durationS
            )
            let expected = vector.expected

            XCTAssertEqual(summary.engineVersion, expected.engineVersion, vector.name)
            XCTAssertEqual(
                summary.durationS, expected.durationS, accuracy: Self.tolerance,
                "\(vector.name) duration")
            XCTAssertEqual(summary.cutCount, expected.cutCount, "\(vector.name) cut count")
            XCTAssertEqual(
                summary.medianShotS, expected.medianShotS, accuracy: Self.tolerance,
                "\(vector.name) median shot")
            XCTAssertEqual(
                summary.cutsPerMinute, expected.cutsPerMinute, accuracy: Self.tolerance,
                "\(vector.name) cuts/min")
            XCTAssertEqual(
                summary.score, expected.score, accuracy: Self.tolerance,
                "\(vector.name) score")
            XCTAssertEqual(summary.label.rawValue, expected.label, "\(vector.name) label")
            assertEqual(
                summary.heatmapBinCentersS, expected.heatmap.binCentersS,
                label: "\(vector.name) heatmap bin centers")
            assertEqual(
                summary.heatmapCutsPerMin, expected.heatmap.cutsPerMin,
                label: "\(vector.name) heatmap cuts/min")
        }
    }

    // MARK: - Helpers

    private func assertEqual(
        _ actual: [Double],
        _ expected: [Double],
        label: String,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertEqual(actual.count, expected.count, "\(label): count", file: file, line: line)
        guard actual.count == expected.count else { return }
        for (i, (a, e)) in zip(actual, expected).enumerated() {
            XCTAssertEqual(a, e, accuracy: Self.tolerance, "\(label)[\(i)]", file: file, line: line)
        }
    }
}
