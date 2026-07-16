// HeatmapStripView.swift
// ASL
//
// Cut-density heat map strip. The image itself is rendered server-side (the
// backend's matplotlib renderer) and delivered as a PNG — the app displays
// it verbatim so every surface shows the identical artifact.

import SwiftUI

struct HeatmapStripView: View {
    let url: URL

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .scaledToFill()
                case .failure:
                    Label("Heat map unavailable", systemImage: "photo")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity)
                case .empty:
                    ProgressView()
                        .frame(maxWidth: .infinity)
                @unknown default:
                    EmptyView()
                }
            }
            .frame(height: Theme.heatmapStripHeight)
            .frame(maxWidth: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            HStack {
                Text("start")
                Spacer()
                Text("cut density across the video (cuts/min)")
                Spacer()
                Text("end")
            }
            .font(.caption2)
            .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Heat map of cut density across the video timeline")
    }
}
