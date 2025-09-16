import pandas as pd
from mrra.data.trajectory import TrajectoryBatch
from mrra.retriever.graph_rag import GraphRAGGenerate

df = pd.DataFrame({
    'user_id': ['u']*2,
    'timestamp': ['2023-01-01 09:00:00','2023-01-01 10:00:00'],
    'latitude': [31.23,31.24],
    'longitude':[121.47,121.48],
})

tb = TrajectoryBatch(df)
ret = GraphRAGGenerate(tb=tb)
print('mobility_graph type =', type(ret.mobility_graph))
print('has G =', hasattr(ret.mobility_graph, 'G'))
