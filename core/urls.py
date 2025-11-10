from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('distribuir-cartelas/', views.distribuir_cartelas, name='distribuir_cartelas'),
    path('cadastrar-cartelas/', views.cadastrar_cartelas, name='cadastrar_cartelas'),
    path('cartelas/cancelar/', views.cancelar_cartela, name='cancelar_cartela'),
    path('cancelamentos/', views.listar_cancelamentos, name='listar_cancelamentos'),
    path('cancelamentos/<int:log_id>/desfazer/', views.desfazer_cancelamento, name='desfazer_cancelamento'),
    path('movimentos/', views.listar_movimentos, name='listar_movimentos'),
    path('movimentos/novo/', views.criar_movimento, name='criar_movimento'),
    path('movimentos/editar/<int:pk>/', views.editar_movimento, name='editar_movimento'),
    path('movimentos/excluir/<int:pk>/', views.excluir_movimento, name='excluir_movimento'),
    path('acertos/registrar/', views.registrar_acerto, name='registrar_acerto'),
    path('acertos/<int:pk>/', views.relatorio_acerto, name='relatorio_acerto'),
    path('acertos/<int:pk>/editar/', views.editar_acerto, name='editar_acerto'),
    path('acertos/<int:pk>/cancelar/', views.cancelar_acerto, name='cancelar_acerto'),
    path('acertos/<int:pk>/relatorio/', views.relatorio_acerto, name='relatorio_acerto'),
    path('acertos/', views.lista_acertos, name='lista_acertos'), 
    #path('api/buscar-cartelas-pendentes/', views.buscar_cartelas_pendentes, name='buscar_cartelas_pendentes'),
    path('api/buscar-cartela-por-numero/', views.buscar_cartela_por_numero_api, name='api_buscar_cartela_por_numero'),
    path('movimento/<int:movimento_id>/historico/', views.historico_movimento, name='historico_movimento'),
    path('cancelamentos/exportar_csv/', views.exportar_canceladas_csv, name='exportar_canceladas_csv'),

]
