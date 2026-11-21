from app.clustering import cluster_vectors


def test_average_linkage_groups_vectors_without_merging_distant_topics():
    items = [([1.0, 0.0], index) for index in range(10)] + [
        ([0.0, 1.0], index) for index in range(10, 20)
    ]

    clusters = cluster_vectors(items)

    assert sorted(sorted(cluster) for cluster in clusters) == [
        list(range(10)),
        list(range(10, 20)),
    ]
