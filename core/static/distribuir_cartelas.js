document.addEventListener('DOMContentLoaded', function() {
    const metodoSequencia = document.getElementById('metodo_sequencia');
    const metodoQuantidade = document.getElementById('metodo_quantidade');
    const camposSequencia = document.getElementById('campos_sequencia');
    const camposQuantidade = document.getElementById('campos_quantidade');
    const numeroInicial = document.getElementById('numero_inicial');
    const numeroFinal = document.getElementById('numero_final');
    const quantidade = document.getElementById('quantidade');
    const movimento = document.getElementById('movimento');
    const btnDistribuir = document.getElementById('btnDistribuir');
    const btnConfirmar = document.getElementById('btnConfirmar');
    const formDistribuir = document.getElementById('formDistribuir');
    const confirmText = document.getElementById('confirmText');
    
    let confirmModal;
    
    // Inicializar modal do Bootstrap
    const modalElement = document.getElementById('confirmModal');
    if (modalElement) {
        // Certifique-se de que 'bootstrap' está disponível globalmente (carregado via script tag)
        confirmModal = new bootstrap.Modal(modalElement); 
    }

    // Função para alternar campos
    function toggleFields() {
        if (metodoSequencia.checked) {
            camposSequencia.style.display = 'block';
            camposQuantidade.style.display = 'none';
            numeroInicial.required = true;
            numeroFinal.required = true;
            quantidade.required = false;
            quantidade.value = '';
        } else {
            camposSequencia.style.display = 'none';
            camposQuantidade.style.display = 'block';
            numeroInicial.required = false;
            numeroFinal.required = false;
            quantidade.required = true;
            numeroInicial.value = '';
            numeroFinal.value = '';
        }
    }

    // Event listeners para os radio buttons
    metodoSequencia.addEventListener('change', toggleFields);
    metodoQuantidade.addEventListener('change', toggleFields);

    // Inicializar estado dos campos
    toggleFields();

    // Validação e exibição do modal
    btnDistribuir.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Validar movimento
        if (!movimento.value) {
            alert('Por favor, selecione um Movimento/Pastoral');
            movimento.focus();
            return;
        }

        let mensagem = '';
        const movimentoNome = movimento.options[movimento.selectedIndex].text;

        if (metodoSequencia.checked) {
            // Validação de sequência
            if (!numeroInicial.value || !numeroFinal.value) { // Verifica se ambos estão preenchidos
                alert('Por favor, preencha os números inicial e final');
                numeroInicial.focus(); // Ou numeroFinal, dependendo do que estiver vazio
                return;
            }

            const inicial = parseInt(numeroInicial.value);
            const final = parseInt(numeroFinal.value);

            if (inicial > final) {
                alert('O número inicial não pode ser maior que o final');
                numeroInicial.focus();
                return;
            }

            // Você pode querer adicionar uma validação para verificar se são números válidos (opcional)
            if (isNaN(inicial) || isNaN(final)) {
                 alert('Por favor, insira números válidos para a sequência.');
                 numeroInicial.focus();
                 return;
            }

            const qtd = final - inicial + 1;
            mensagem = `Confirma a distribuição de <strong>${qtd} cartelas</strong> (${inicial} a ${final}) para <strong>${movimentoNome}</strong>?`;
            
        } else { // metodoQuantidade.checked
            // Validação de quantidade
            if (!quantidade.value || parseInt(quantidade.value) <= 0 || isNaN(parseInt(quantidade.value))) {
                alert('Por favor, informe uma quantidade válida');
                quantidade.focus();
                return;
            }

            mensagem = `Confirma a distribuição de <strong>${quantidade.value} cartelas</strong> para <strong>${movimentoNome}</strong>?`;
        }

        // Se chegou até aqui, a validação passou
        confirmText.innerHTML = mensagem;
        if (confirmModal) {
            confirmModal.show();
        } else {
            // Caso o modal não tenha sido inicializado corretamente (improvável se o HTML estiver certo)
            console.error('Modal do Bootstrap não foi inicializado.');
            // Opcional: enviar o formulário diretamente se o modal for crucial
            // formDistribuir.submit(); 
        }
    });

    // Confirmar e enviar formulário
    btnConfirmar.addEventListener('click', function() {
        if (confirmModal) {
            confirmModal.hide();
        }
        formDistribuir.submit();
    });
});