from django.shortcuts import render, redirect
from django.conf import settings
from .models import Cartela, Movimento, Acerto
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .forms import MovimentoForm, AcertoForm, CancelamentoLoteForm
from django.core.paginator import Paginator
from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Count, Q, Sum, F, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Cartela, Movimento, Distribuicao, LogCancelamento
from .forms import CancelamentoForm
import re
import csv
from django.http import HttpResponse

from django.db.models import Count, Q # Importe Q

def dashboard(request):
    # --- CÁLCULOS PARA OS CARDS SUPERIORES ---
    total_cadastradas = Cartela.objects.count()
    total_distribuido_geral = Distribuicao.objects.aggregate(total=Sum('quantidade'))['total'] or 0
    total_acertadas_vendidas = Cartela.objects.filter(status='ACERTADA').count()
    total_devolvidas = Cartela.objects.filter(status='DEVOLVIDA').count()
    total_cortesias = Cartela.objects.filter(status='CORTESIA').count()
    total_disponivel_estoque = Cartela.objects.filter(status='DISPONIVEL').count()
    total_pendente_acerto = Cartela.objects.filter(status='DISTRIBUIDA').count()

    # --- CÁLCULOS PARA A TABELA DE MOVIMENTOS (GRID) ---
    query = request.GET.get('q')
    movimentos_qs = Movimento.objects.all()

    if query:
        movimentos_qs = movimentos_qs.filter(nome__icontains=query)

    movimentos_list = movimentos_qs.annotate(
        cartelas_distribuidas_venda=Sum('distribuicoes__quantidade', distinct=True, output_field=IntegerField()),
        cartelas_vendidas=Count('acertos__cartelas_vendidas', distinct=True),
        cartelas_devolvidas=Count('acertos__cartelas_devolvidas', distinct=True),
        cartelas_cortesia=Count('acertos__cartelas_cortesia', distinct=True),
    ).order_by('-id')

    # --- CÁLCULO FINAL EM PYTHON COM A REGRA DE NEGÓCIO CORRETA ---
    for movimento in movimentos_list:
        distribuidas = movimento.cartelas_distribuidas_venda or 0
        vendidas = movimento.cartelas_vendidas or 0
        devolvidas = movimento.cartelas_devolvidas or 0
        
        # --- CORREÇÃO APLICADA AQUI ---
        # As cortesias não são mais subtraídas do saldo pendente da pastoral.
        movimento.cartelas_pendentes = distribuidas - (vendidas + devolvidas)

    context = {
        'total_cadastradas': total_cadastradas,
        'total_distribuido_geral': total_distribuido_geral,
        'total_acertadas_vendidas': total_acertadas_vendidas,
        'total_devolvidas': total_devolvidas,
        'total_cortesias': total_cortesias,
        'total_disponivel_estoque': total_disponivel_estoque,
        'total_pendente_acerto': total_pendente_acerto,
        'query': query,
        'movimentos': movimentos_list,
    }
    return render(request, 'core/dashboard.html', context)

@transaction.atomic # Garante a integridade dos dados: ou tudo ou nada.
def distribuir_cartelas(request):
    if request.method == 'POST':
        movimento_id = request.POST.get('movimento')
        metodo = request.POST.get('metodo_distribuicao')
        membro = request.POST.get('membro_responsavel')
        
        # Validação básica inicial
        if not movimento_id or not metodo:
            messages.error(request, "Movimento e método de distribuição são obrigatórios.")
            return redirect('distribuir_cartelas')

        movimento = get_object_or_404(Movimento, id=movimento_id)
        cartelas_para_distribuir = []
        quantidade_solicitada = 0
        

        # --- Lógica para cada método ---
        if metodo == 'quantidade':
            try:
                quantidade = int(request.POST.get('quantidade', 0))
                if quantidade <= 0:
                    raise ValueError("A quantidade deve ser positiva.")
                quantidade_solicitada = quantidade
                
                cartelas_para_distribuir = list(Cartela.objects.filter(
                    status='DISPONIVEL'
                ).order_by('numero')[:quantidade])

            except (ValueError, TypeError):
                messages.error(request, "Por favor, insira uma quantidade numérica válida.")
                return redirect('distribuir_cartelas')

        elif metodo == 'sequencia':
            try:
                num_inicial = request.POST.get('numero_inicial')
                num_final = request.POST.get('numero_final')
                if not num_inicial or not num_final:
                    raise ValueError("Número inicial e final são obrigatórios.")

                # Valida se são números
                inicial = int(num_inicial)
                final = int(num_final)

                if inicial > final:
                    messages.error(request, "O número inicial não pode ser maior que o final.")
                    return redirect('distribuir_cartelas')
                
                quantidade_solicitada = (final - inicial) + 1
                
                cartelas_para_distribuir = list(Cartela.objects.filter(
                    numero__gte=str(inicial).zfill(4),
                    numero__lte=str(final).zfill(4),
                    status='DISPONIVEL'
                ).order_by('numero'))

            except (ValueError, TypeError):
                messages.error(request, "Por favor, insira números válidos para a sequência.")
                return redirect('distribuir_cartelas')

        # --- Validação e Processamento ---
        
        # Verifica se foram encontradas cartelas
        if not cartelas_para_distribuir:
            messages.warning(request, "Nenhuma cartela disponível foi encontrada para os critérios informados.")
            return redirect('distribuir_cartelas')

        # Se o método for 'quantidade', verifica se a quantidade encontrada é suficiente
        if metodo == 'quantidade' and len(cartelas_para_distribuir) < quantidade_solicitada:
            messages.error(request, f"Operação cancelada. Há apenas {len(cartelas_para_distribuir)} cartelas disponíveis, mas você solicitou {quantidade_solicitada}.")
            return redirect('distribuir_cartelas')

        # --- SUCESSO! A PARTE MAIS IMPORTANTE ---

        # 1. Cria o registro histórico da distribuição
        distribuicao_hist = Distribuicao.objects.create(
            movimento=movimento,
            quantidade=len(cartelas_para_distribuir),
            membro_responsavel=membro
        )
        # Adiciona as cartelas ao registro histórico
        distribuicao_hist.cartelas.set(cartelas_para_distribuir)

        # 2. Atualiza o status e o movimento de cada cartela
        ids_para_atualizar = [c.id for c in cartelas_para_distribuir]
        Cartela.objects.filter(id__in=ids_para_atualizar).update(
            status='DISTRIBUIDA',
            movimento=movimento,
            data_distribuicao=distribuicao_hist.data_distribuicao
        )

        messages.success(request, f"{len(cartelas_para_distribuir)} cartelas distribuídas com sucesso para {movimento.nome}.")
        return redirect('distribuir_cartelas') # Redireciona para a mesma página para ver o histórico

    # --- Lógica para o método GET (carregar a página) ---
    movimentos = Movimento.objects.order_by('nome')
    total_disponivel = Cartela.objects.filter(status='DISPONIVEL').count()
    
    # Adiciona as últimas distribuições para exibir na tabela
    ultimas_distribuidas = Distribuicao.objects.order_by('-data_distribuicao')[:10]

    context = {
        'movimentos': movimentos,
        'cartelas_disponiveis': total_disponivel,
        'ultimas_distribuidas': ultimas_distribuidas
    }
    return render(request, 'core/distribuir_cartelas.html', context)

def cadastrar_cartelas(request):
    if request.method == 'POST':
        inicio = int(request.POST.get('inicio', 1))
        fim = int(request.POST.get('fim', 1))
        
        # Validação básica
        if fim < inicio:
            messages.error(request, "O número final deve ser maior que o inicial!")
            return redirect('cadastrar_cartelas')
        
        # Verifica se há conflitos
        if Cartela.objects.filter(numero__gte=f"{inicio:04d}", numero__lte=f"{fim:04d}").exists():
            messages.error(request, "Algumas cartelas deste intervalo já existem!")
            return redirect('cadastrar_cartelas')
        
        # Cria as cartelas
        cartelas = [
            Cartela(numero=f"{i:04d}", status="DISPONIVEL")
            for i in range(inicio, fim + 1)
        ]
        Cartela.objects.bulk_create(cartelas)
        messages.success(request, f"{len(cartelas)} cartelas cadastradas (de {inicio:04d} a {fim:04d})!")
        return redirect('dashboard')
    
    return render(request, 'core/cadastrar_cartelas.html')

def listar_cartelas(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    data = request.GET.get('date', '')
    
    cartelas = Cartela.objects.all()
    
    if query:
        cartelas = cartelas.filter(
            Q(numero__icontains=query) |
            Q(movimento__nome__icontains=query)
        )
    
    if status:
        cartelas = cartelas.filter(status=status)
        
    if data:
        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d').date()
            cartelas = cartelas.filter(data_distribuicao__date=data_obj)
        except ValueError:
            pass
    
    context = {
        'cartelas': cartelas,
        'filter_status': status,
        'filter_date': data,
        'search_query': query
    }
    return render(request, 'core/cartelas/listar.html', context)

def listar_movimentos(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    
    movimentos_list = Movimento.objects.all().order_by('nome')
    
    # Aplicar filtros
    if query:
        movimentos_list = movimentos_list.filter(nome__icontains=query)
    
    # Paginação
    paginator = Paginator(movimentos_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/movimentos/listar.html', {
        'movimentos': page_obj.object_list,
        'page_obj': page_obj,
        'search_query': query,
        'filter_status': status_filter,
        'filter_date': date_filter
    })


def criar_movimento(request):
    if request.method == 'POST':
        form = MovimentoForm(request.POST)
        if form.is_valid():
            movimento = form.save()
            messages.success(request, f'Movimento "{movimento.nome}" criado com sucesso!')
            return redirect('listar_movimentos')
    else:
        form = MovimentoForm()
    
    return render(request, 'core/movimentos/form.html', {
        'form': form,
        'titulo': 'Novo Movimento'
    })

def editar_movimento(request, pk):
    movimento = get_object_or_404(Movimento, pk=pk)
    if request.method == 'POST':
        form = MovimentoForm(request.POST, instance=movimento)
        if form.is_valid():
            form.save()
            messages.success(request, f'Movimento "{movimento.nome}" atualizado!')
            return redirect('listar_movimentos')
    else:
        form = MovimentoForm(instance=movimento)
    
    return render(request, 'core/movimentos/form.html', {
        'form': form,
        'titulo': f'Editar {movimento.nome}'
    })

def excluir_movimento(request, pk):
    movimento = get_object_or_404(Movimento, pk=pk)
    if request.method == 'POST':
        nome = movimento.nome
        movimento.delete()
        messages.success(request, f'Movimento "{nome}" excluído!')
        return redirect('listar_movimentos')
    
    return render(request, 'core/movimentos/confirmar_exclusao.html', {
        'movimento': movimento
    })

def registrar_acerto(request):
    if request.method == 'POST':
        # Coleta de dados do formulário
        movimento_id = request.POST.get('movimento')
        membro_pastoral = request.POST.get('membro_pastoral')
        observacoes = request.POST.get('observacoes')
        tipo_pagamento = request.POST.get('tipo_pagamento')
        cortesia_ids = request.POST.getlist('cartelas_cortesia_ids[]') # IDs das cartelas de cortesia selecionadas

        try:
            qtd_vendidas = int(request.POST.get('qtd_vendidas', 0))
            # O campo devolvidas é opcional, se vier vazio, consideramos 0
            qtd_devolvidas = int(request.POST.get('qtd_devolvidas') or 0)
            valor_recebido_str = request.POST.get('valor_recebido', '0.0').replace('.', '').replace(',', '.')
            valor_recebido = Decimal(valor_recebido_str)
        except (ValueError, TypeError):
            messages.error(request, "Valores numéricos inválidos.")
            return redirect('registrar_acerto')

        movimento = get_object_or_404(Movimento, id=movimento_id)
        
        # Inicia a transação atômica
        try:
            with transaction.atomic():
                # Busca as cartelas que estão com o movimento
                cartelas_pendentes = list(Cartela.objects.filter(movimento=movimento, status='DISTRIBUIDA').order_by('numero'))
                
                if (qtd_vendidas + qtd_devolvidas) > len(cartelas_pendentes):
                    messages.error(request, "A soma de cartelas vendidas e devolvidas excede o total pendente.")
                    # Como a transação falhou, o redirect é seguro
                    return redirect('registrar_acerto')

                cartelas_a_vender_objs = cartelas_pendentes[:qtd_vendidas]
                cartelas_a_devolver_objs = cartelas_pendentes[qtd_vendidas : qtd_vendidas + qtd_devolvidas]
                
                # Cálculo de valores
                valor_unitario = Decimal('40.00')
                valor_total_pago = qtd_vendidas * valor_unitario
                
                # 1. Cria o objeto Acerto primeiro
                acerto = Acerto.objects.create(
                    movimento=movimento,
                    membro_pastoral=membro_pastoral,
                    observacoes=observacoes,
                    valor_total=valor_total_pago,
                    valor_recebido=valor_recebido,
                    tipo_pagamento=tipo_pagamento
                )
                
                # 2. Processa as cartelas VENDIDAS
                for cartela in cartelas_a_vender_objs:
                    cartela.status = 'ACERTADA'
                    cartela.data_acerto = timezone.now().date()
                Cartela.objects.bulk_update(cartelas_a_vender_objs, ['status', 'data_acerto'])
                acerto.cartelas_vendidas.set(cartelas_a_vender_objs)

                # 3. Processa as cartelas DEVOLVIDAS
                if cartelas_a_devolver_objs:
                    for cartela in cartelas_a_devolver_objs:
                        cartela.status = 'DEVOLVIDA' # Status ajustado
                        cartela.movimento = None
                        cartela.data_acerto = timezone.now().date() # Data da devolução
                    Cartela.objects.bulk_update(cartelas_a_devolver_objs, ['status', 'movimento', 'data_acerto'])
                    acerto.cartelas_devolvidas.set(cartelas_a_devolver_objs)

                # 4. Processa as cartelas de CORTESIA
                if cortesia_ids:
                    cartelas_cortesia_objs = Cartela.objects.filter(id__in=cortesia_ids, status='DISPONIVEL')
                    for cartela in cartelas_cortesia_objs:
                        cartela.status = 'CORTESIA'
                        cartela.movimento = movimento # Associa ao movimento que ganhou
                        cartela.data_distribuicao = timezone.now().date()
                    Cartela.objects.bulk_update(cartelas_cortesia_objs, ['status', 'movimento', 'data_distribuicao'])
                    acerto.cartelas_cortesia.set(cartelas_cortesia_objs)
                
                messages.success(request, f"Acerto de {movimento.nome} registrado com sucesso!")
                return redirect('relatorio_acerto', pk=acerto.pk)

        except Exception as e:
            messages.error(request, f"Ocorreu um erro durante a transação: {e}")
            return redirect('registrar_acerto')

    # Lógica para o GET (carregar a página)
    movimentos = Movimento.objects.annotate(
        cartelas_pendentes=Count('cartelas', filter=Q(cartelas__status='DISTRIBUIDA'))
    ).filter(cartelas_pendentes__gt=0).order_by('nome')
    
    context = {
        'movimentos': movimentos,
        'tipos_pagamento': Acerto.TIPO_PAGAMENTO
    }
    return render(request, 'core/acertos/registrar.html', context)

def cancelar_acerto(request, pk):
    acerto = get_object_or_404(Acerto, pk=pk)

    if request.method == 'POST':
        # --- LÓGICA DE CANCELAMENTO CORRIGIDA ---

        # 1. Reverte o status das cartelas de venda e devolução para 'DISTRIBUIDA'
        acerto.cartelas_vendidas.all().update(status='DISTRIBUIDA')
        acerto.cartelas_devolvidas.all().update(status='DISTRIBUIDA')

        # 2. <<< CORREÇÃO AQUI >>>
        # Reverte o status das cartelas de cortesia para 'DISPONIVEL', 
        # devolvendo-as ao estoque geral e não para a pendência do membro.
        acerto.cartelas_cortesia.all().update(status='DISPONIVEL')

        # 3. Agora que as cartelas estão com seus status corretos, podemos deletar o acerto
        acerto.delete()

        # 4. Redireciona o usuário de volta para a lista de acertos
        return redirect('lista_acertos')

    # Se não for POST, apenas mostra a página de confirmação
    context = {
        'acerto': acerto
    }
    return render(request, 'core/acertos/cancelar_acerto_confirm.html', context)

def relatorio_acerto(request, pk): 
    # 2. Usando 'pk' para buscar o objeto correto
    acerto = get_object_or_404(Acerto, id=pk)

    # Pega o valor da cartela do settings.py
    valor_unitario_cartela = settings.VALOR_CARTELA

    # Calcula o troco (usando Decimal para segurança)
    valor_recebido = Decimal(acerto.valor_recebido) if acerto.valor_recebido else Decimal(0)
    valor_total = Decimal(acerto.valor_total) if acerto.valor_total else Decimal(0)
    troco_calculado = valor_recebido - valor_total

    context = {
        'acerto': acerto,
        'valor_cartela': valor_unitario_cartela,
        'troco': troco_calculado,
    }

    

    return render(request, 'core/acertos/relatorio.html', context)

def editar_acerto(request, pk):
    acerto = get_object_or_404(Acerto, pk=pk)

    if request.method == 'POST':
        form = AcertoForm(request.POST, instance=acerto)
        if form.is_valid():
            # Não precisamos mais de lógicas complexas de reverter status aqui.
            # A lógica de ajuste de status será feita na view de registro e cancelamento.
            # A edição apenas ajusta os números do PRÓPRIO acerto.
            
            acerto_editado = form.save(commit=False)
            
            # Recalcula o valor total com base na nova quantidade
            valor_unitario = settings.VALOR_CARTELA
            acerto_editado.valor_total = acerto_editado.quantidade_vendidas * valor_unitario
            acerto_editado.save()

            # ATENÇÃO: A lógica de ajustar o status das cartelas foi simplificada.
            # O ideal é que a edição apenas corrija os valores e um "reprocessamento"
            # do movimento seja feito. Por enquanto, a edição apenas corrige o registro em si.
            # A lógica de status será tratada no registro e cancelamento.

            return redirect('lista_acertos')
    else:
        form = AcertoForm(instance=acerto)

    context = {
        'form': form,
        'acerto': acerto
    }
    return render(request, 'core/acertos/editar_acerto.html', context)

def lista_acertos(request):
    query = request.GET.get('q', '')
    
    # Começa com todos os acertos, ordenados do mais recente para o mais antigo
    acertos_list = Acerto.objects.all().order_by('-data')

    if query:
        # Filtra a lista se houver uma busca.
        # Procura no nome do movimento OU no nome do membro pastoral.
        acertos_list = acertos_list.filter(
            Q(movimento__nome__icontains=query) |
            Q(membro_pastoral__icontains=query)
        )

    context = {
        'acertos': acertos_list,
        'query': query,
    }
    return render(request, 'core/acertos/lista_acertos.html', context)

def buscar_cartelas_pendentes(request):
    movimento_id = request.GET.get('movimento_id')
    cartelas = Cartela.objects.filter(movimento_id=movimento_id, status='DISTRIBUIDA').order_by('numero')
    # Retorna os dados em formato JSON para o JavaScript
    data = list(cartelas.values('id', 'numero'))
    return JsonResponse(data, safe=False)

def buscar_cartela_por_numero_api(request):
    """
    API que busca uma cartela pelo número, verificando se ela está disponível para cortesia.
    """
    numero_cartela = request.GET.get('numero')
    if not numero_cartela:
        return JsonResponse({'error': 'Número da cartela não fornecido.'}, status=400)

    try:
        # Busca a cartela pelo número e verifica o status
        cartela = Cartela.objects.get(numero=numero_cartela, status='DISPONIVEL')
        # Retorna os dados da cartela se encontrada e disponível
        return JsonResponse({
            'id': cartela.id,
            'numero': cartela.numero
        })
    except Cartela.DoesNotExist:
        # Se não encontrar ou o status não for 'DISPONIVEL'
        return JsonResponse({'error': f'Cartela "{numero_cartela}" não encontrada, já foi vendida ou distribuída.'}, status=404)
    
def historico_movimento(request, movimento_id):
    movimento = get_object_or_404(Movimento, id=movimento_id)

    distribuicoes = Distribuicao.objects.filter(movimento=movimento).order_by('data_distribuicao')
    acertos = Acerto.objects.filter(movimento=movimento).order_by('data') 

    historico = []

    
    for d in distribuicoes:
        historico.append({
            'id': d.id,  
            'data': d.data_distribuicao,
            'tipo': 'Distribuição',
            'descricao': f"Pegou {d.quantidade} cartelas.",
            'ator': 'Sistema' 
        })

    # --- E CONFIRMAMOS AQUI ---
    for a in acertos:
        vendidas = a.cartelas_vendidas.count()
        devolvidas = a.cartelas_devolvidas.count()
        
        historico.append({
            'id': a.id, 
            'data': a.data,
            'tipo': 'Acerto',
            'descricao': f"Acertou {vendidas} vendidas e {devolvidas} devolvidas.",
            'ator': a.membro_pastoral if a.membro_pastoral else 'Não informado'
        })

    historico_ordenado = sorted(historico, key=lambda item: item['data'], reverse=True)

    cartelas_pendentes_atuais = movimento.cartelas.filter(status='DISTRIBUIDA').count()

    context = {
        'movimento': movimento,
        'historico': historico_ordenado,
        'saldo_pendente': cartelas_pendentes_atuais,
    }

    return render(request, 'core/historico_movimento.html', context)

@transaction.atomic
def cancelar_cartela(request):
    form = CancelamentoForm()
    form_lote = CancelamentoLoteForm()

    if request.method == 'POST':
        # --- LÓGICA 1: FOI ENVIADO O FORMULÁRIO INDIVIDUAL ---
        if 'submit_individual' in request.POST:
            form = CancelamentoForm(request.POST)
            if form.is_valid():
                # Esta parte é a mesma lógica que já tínhamos
                numero_cartela = form.cleaned_data['numero_cartela']
                motivo = form.cleaned_data['motivo']
                # ... (restante da lógica individual que já funciona) ...
                try:
                    cartela_a_cancelar = Cartela.objects.get(numero=str(numero_cartela).zfill(4))
                    # ... (validações de status etc) ...
                    if cartela_a_cancelar.status == 'CANCELADA':
                        messages.warning(request, f"A cartela '{numero_cartela}' já está cancelada.")
                        return redirect('cancelar_cartela')
                    if cartela_a_cancelar.status == 'DISPONIVEL':
                        messages.error(request, f"Não é possível cancelar uma cartela que ainda está no estoque ('Disponível').")
                        return redirect('cancelar_cartela')

                    status_anterior_raw = cartela_a_cancelar.status
                    movimento_anterior_obj = cartela_a_cancelar.movimento
                    status_anterior_display = cartela_a_cancelar.get_status_display()
                    log = LogCancelamento(cartela=cartela_a_cancelar, motivo=motivo, status_anterior=status_anterior_raw, movimento_anterior=movimento_anterior_obj)
                    cartela_a_cancelar.status = 'CANCELADA'
                    cartela_a_cancelar.movimento = None
                    cartela_a_cancelar.data_distribuicao = None
                    cartela_a_cancelar.save()
                    log.save()
                    messages.success(request, f"Cartela '{numero_cartela}' (status anterior: {status_anterior_display}) foi cancelada com sucesso!")
                except Cartela.DoesNotExist:
                    messages.error(request, f"A cartela de número '{numero_cartela}' não foi encontrada.")
                
                return redirect('cancelar_cartela')

        # --- LÓGICA 2: FOI ENVIADO O FORMULÁRIO EM LOTE ---
        elif 'submit_lote' in request.POST:
            form_lote = CancelamentoLoteForm(request.POST)
            if form_lote.is_valid():
                numeros_str = form_lote.cleaned_data['numeros_cartelas']
                motivo = form_lote.cleaned_data['motivo']
                
                # Limpa e separa os números. Remove entradas vazias.
                numeros_list = [num for num in re.split(r'[\s,]+', numeros_str) if num]
                
                sucessos = []
                falhas = []

                for num in numeros_list:
                    try:
                        cartela = Cartela.objects.get(numero=str(num).zfill(4))
                        if cartela.status == 'CANCELADA':
                            falhas.append(f"'{num}' (já estava cancelada)")
                        elif cartela.status == 'DISPONIVEL':
                            falhas.append(f"'{num}' (está no estoque)")
                        else:
                            # Tudo certo para cancelar
                            log = LogCancelamento(cartela=cartela, motivo=motivo, status_anterior=cartela.status, movimento_anterior=cartela.movimento)
                            cartela.status = 'CANCELADA'
                            cartela.movimento = None
                            cartela.data_distribuicao = None
                            cartela.save()
                            log.save()
                            sucessos.append(num)
                    except Cartela.DoesNotExist:
                        falhas.append(f"'{num}' (não encontrada)")
                
                # Monta as mensagens de feedback
                if sucessos:
                    messages.success(request, f"{len(sucessos)} cartela(s) cancelada(s) com sucesso: {', '.join(sucessos)}.")
                if falhas:
                    messages.error(request, f"{len(falhas)} cartela(s) não puderam ser canceladas: {'; '.join(falhas)}.")

                return redirect('cancelar_cartela')

    # Lógica GET (quando a página é apenas carregada)
    ultimos_cancelamentos = LogCancelamento.objects.order_by('-data_cancelamento')[:10]
    context = {
        'form': form,
        'form_lote': form_lote, # Passa o novo formulário para o template
        'ultimos_cancelamentos': ultimos_cancelamentos,
    }
    return render(request, 'core/cancelar_cartela.html', context)

def listar_cancelamentos(request):
    """
    Exibe uma lista paginada de todos os logs de cancelamento,
    com funcionalidade de pesquisa pelo número da cartela.
    """
    # Pega o termo de busca da URL (ex: /cancelamentos/?q=1234)
    query = request.GET.get('q', '')

    # Começa com todos os logs, ordenados pelos mais recentes
    # Usamos select_related para otimizar a busca, evitando múltiplas queries ao banco
    logs_list = LogCancelamento.objects.select_related('cartela', 'movimento_anterior').order_by('-data_cancelamento')

    # Se houver um termo de busca, filtra a lista
    if query:
        logs_list = logs_list.filter(cartela__numero__icontains=query)

    context = {
        'cancelamentos': logs_list,
        'query_atual': query,  # Para manter o valor no campo de busca
    }
    return render(request, 'core/listar_cancelamentos.html', context)

@require_POST  # Garante que esta view só aceita requisições POST
@transaction.atomic  # Garante que todas as operações com o banco ou funcionam ou são revertidas
def desfazer_cancelamento(request, log_id):
    """
    Reverte uma operação de cancelamento.
    Restaura o status e o movimento da cartela e apaga o log de cancelamento.
    """
    # 1. Encontra o log de cancelamento específico, ou retorna um erro 404 se não existir
    log = get_object_or_404(LogCancelamento, id=log_id)
    cartela = log.cartela

    # 2. Restaura a cartela usando os dados guardados no log
    cartela.status = log.status_anterior
    cartela.movimento = log.movimento_anterior
    cartela.save()

    # 3. Apaga o log de cancelamento, pois a operação foi desfeita
    log.delete()

    # 4. Envia uma mensagem de sucesso para o usuário
    messages.success(request, f"O cancelamento da cartela '{cartela.numero}' foi desfeito com sucesso.")

    # 5. Redireciona o usuário de volta para a lista
    return redirect('listar_cancelamentos')

def exportar_canceladas_csv(request):
    """
    Gera um arquivo CSV mais legível e profissional.
    """
    # Define o charset para utf-8-sig, que inclui o BOM (Byte Order Mark).
    # Isso ajuda o Excel a entender que o arquivo usa acentos (UTF-8).
    response = HttpResponse(
        content_type='text/csv; charset=utf-8-sig',
        headers={'Content-Disposition': 'attachment; filename="relatorio_canceladas.csv"'},
    )

    # --- MELHORIA 1: Usar ponto e vírgula como delimitador ---
    # O `delimiter=';'` é a chave para o Excel abrir corretamente em colunas.
    writer = csv.writer(response, delimiter=';')

    # --- MELHORIA 2: Adicionar Título e Data de Emissão ---
    writer.writerow(['Relatório de Cartelas Canceladas'])
    
    # Pega a data e hora atual no fuso horário correto
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')
    writer.writerow([f'Gerado em: {data_emissao}'])
    
    # Adiciona uma linha em branco para separar o cabeçalho dos dados
    writer.writerow([]) 

    # --- Cabeçalho dos Dados ---
    writer.writerow([
        'Numero da Cartela',
        'Pastoral/Movimento',
        'Motivo do Cancelamento'
    ])

    # Busca no banco de dados
    logs = LogCancelamento.objects.select_related('cartela', 'movimento_anterior').order_by('data_cancelamento')

    # Escreve os dados
    for log in logs:
        writer.writerow([
            log.cartela.numero,
            log.movimento_anterior.nome if log.movimento_anterior else 'N/A',
            log.motivo
        ])

    return response