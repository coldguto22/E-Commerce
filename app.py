from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3

app = Flask(__name__)
app.secret_key = "chave_secreta_para_sessao"

# Configuração do Banco de Dados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'e-commerce.db')

def db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Página Inicial - Home
@app.route('/')
def home():
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nome, descricao, preco, imagem
        FROM produtos
    """)
    produtos = cursor.fetchall()
    conn.close()
    return render_template('home.html', produtos=produtos)

# Gerenciamento de Clientes
@app.route('/clientes')
def clientes():
    conn = db_connection()
    conn.row_factory = sqlite3.Row  # Garante que as linhas retornadas são acessíveis por nome de coluna
    cursor = conn.cursor()

    # Buscar todos os clientes
    cursor.execute("SELECT id, nome, email, telefone FROM clientes")
    clientes = [dict(row) for row in cursor.fetchall()]  # Converte cada linha em um dicionário

    # Buscar endereços de cada cliente
    for cliente in clientes:
        cliente_id = cliente['id']
        
        # Certifique-se de iniciar com uma lista vazia para evitar acumulação
        cliente['enderecos'] = []  

        cursor.execute("""
            SELECT tipo, logradouro, numero, complemento, bairro, cidade, estado, cep
            FROM enderecos
            WHERE cliente_id = ?
        """, (cliente_id,))  # Certifique-se de passar o ID correto
        cliente['enderecos'] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return render_template('clientes.html', clientes=clientes)

@app.route('/add_cliente', methods=['POST'])
def add_cliente():
    nome = request.form['nome']
    email = request.form['email']
    telefone = request.form['telefone']

    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO clientes (nome, email, telefone) VALUES (?, ?, ?)", (nome, email, telefone))
    conn.commit()
    conn.close()
    return redirect(url_for('clientes'))

@app.route('/add_endereco', methods=['POST'])
def add_endereco():
    cliente_id = request.form['cliente_id']
    tipo = request.form['tipo']
    logradouro = request.form['logradouro']
    numero = request.form['numero']
    complemento = request.form.get('complemento', None)
    bairro = request.form['bairro']
    cidade = request.form['cidade']
    estado = request.form['estado']
    cep = request.form['cep']

    conn = db_connection()
    cursor = conn.cursor()

    # Insere o endereço na tabela
    cursor.execute("""
        INSERT INTO enderecos (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep))
    conn.commit()
    conn.close()

    return redirect(url_for('clientes'))

# Gerenciamento de Produtos
@app.route('/produtos')
def produtos():
    conn = db_connection()
    cursor = conn.cursor()

    # Buscar os produtos
    cursor.execute("""
        SELECT produtos.id, produtos.nome, produtos.descricao, produtos.preco, categorias_produtos.nome AS categoria
        FROM produtos
        LEFT JOIN categorias_produtos ON produtos.categoria_id = categorias_produtos.id
    """)
    produtos = cursor.fetchall()

    # Buscar as categorias para o dropdown
    cursor.execute("SELECT id, nome FROM categorias_produtos")
    categorias = cursor.fetchall()

    conn.close()
    return render_template('produtos.html', produtos=produtos, categorias=categorias)


@app.route('/add_produto', methods=['POST'])
def add_produto():
    nome = request.form['nome']  # Nome do produto
    descricao = request.form['descricao']  # Descrição do produto
    preco = request.form['preco']  # Preço do produto
    estoque = request.form['estoque']  # Quantidade de estoque
    categoria_id = request.form['categoria_id']  # ID da categoria selecionada no dropdown

    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO produtos (nome, descricao, preco, estoque, categoria_id) VALUES (?, ?, ?, ?, ?)", 
        (nome, descricao, preco, estoque, categoria_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('produtos'))

# Filtro de Produtos
@app.route('/filtro', methods=['GET', 'POST'])
def filtro():
    conn = db_connection()
    cursor = conn.cursor()

    # Buscar categorias para o dropdown
    cursor.execute("SELECT id, nome FROM categorias_produtos")
    categorias = cursor.fetchall()

    resultados = []
    if request.method == 'POST':
        nome = request.form.get('nome', '')
        preco_min = request.form.get('preco_min', None)
        preco_max = request.form.get('preco_max', None)
        categoria_id = request.form.get('categoria_id', '')

        query = """
            SELECT produtos.id, produtos.nome, produtos.descricao, produtos.preco, categorias_produtos.nome AS categoria
            FROM produtos
            LEFT JOIN categorias_produtos ON produtos.categoria_id = categorias_produtos.id
            WHERE 1=1
        """
        params = []
        if nome:
            query += " AND produtos.nome LIKE ?"
            params.append(f"%{nome}%")
        if preco_min:
            query += " AND produtos.preco >= ?"
            params.append(preco_min)
        if preco_max:
            query += " AND produtos.preco <= ?"
            params.append(preco_max)
        if categoria_id:
            query += " AND produtos.categoria_id = ?"
            params.append(categoria_id)

        cursor.execute(query, params)
        resultados = cursor.fetchall()

    conn.close()
    return render_template('filtro.html', categorias=categorias, resultados=resultados)

# Rota para adicionar um item ao carrinho
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, preco FROM produtos WHERE id = ?", (product_id,))
    produto = cursor.fetchone()
    conn.close()

    if not produto:
        return "Produto não encontrado", 404

    # Inicializar o carrinho se não existir
    if 'cart' not in session:
        session['cart'] = []

    # Verificar se o produto já está no carrinho
    for item in session['cart']:
        if item['id'] == product_id:
            item['quantidade'] += 1
            break
    else:
        # Adicionar novo item ao carrinho
        session['cart'].append({
            'id': produto['id'],
            'nome': produto['nome'],
            'preco': produto['preco'],
            'quantidade': 1
        })

    session.modified = True
    return redirect(url_for('view_cart'))

# Rota para visualizar o carrinho
@app.route('/cart')
def view_cart():
    return render_template('cart.html', cart=session.get('cart', []))

# Rota para remover um item do carrinho
@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['id'] != product_id]
        session.modified = True
    return redirect(url_for('view_cart'))

# Rota para finalizar o pedido
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    conn = db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        forma_pagamento_id = request.form['forma_pagamento_id']
        cart = session.get('cart', [])

        if not cart:
            return "Carrinho está vazio", 400

        # Verifica se um novo endereço foi enviado
        if request.form.get('logradouro'):
            tipo = request.form['tipo']
            logradouro = request.form['logradouro']
            numero = request.form['numero']
            complemento = request.form.get('complemento', None)
            bairro = request.form['bairro']
            cidade = request.form['cidade']
            estado = request.form['estado']
            cep = request.form['cep']

            # Insere o novo endereço na tabela
            cursor.execute("""
                INSERT INTO enderecos (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cliente_id, tipo, logradouro, numero, complemento, bairro, cidade, estado, cep))
            endereco_entrega_id = cursor.lastrowid
        else:
            endereco_entrega_id = request.form['endereco_entrega_id']

        # Calcular total do pedido
        total = sum(item['preco'] * item['quantidade'] for item in cart)

        # Inserir o pedido
        cursor.execute("""
            INSERT INTO pedidos (cliente_id, endereco_entrega_id, forma_pagamento_id, total)
            VALUES (?, ?, ?, ?)
        """, (cliente_id, endereco_entrega_id, forma_pagamento_id, total))
        pedido_id = cursor.lastrowid

        # Inserir itens do pedido
        for item in cart:
            cursor.execute("""
                INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
                VALUES (?, ?, ?, ?)
            """, (pedido_id, item['id'], item['quantidade'], item['preco']))

        conn.commit()
        conn.close()

        # Limpar o carrinho
        session.pop('cart', None)

        return redirect(url_for('clientes'))

    # Buscar clientes, formas de pagamento e endereços
    cursor.execute("SELECT id, nome FROM clientes")
    clientes = cursor.fetchall()
    cursor.execute("SELECT id, tipo FROM formas_pagamento")
    formas_pagamento = cursor.fetchall()
    cursor.execute("SELECT id, logradouro || ', ' || numero || ' - ' || cidade AS endereco FROM enderecos")
    enderecos = cursor.fetchall()
    conn.close()

    return render_template('checkout.html', clientes=clientes, formas_pagamento=formas_pagamento, enderecos=enderecos)

if __name__ == "__main__":
    app.run(debug=True)
