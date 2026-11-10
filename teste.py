"""Legacy manual operation. The regression suite is in tests/."""
if __name__ == '__main__':
    from core.jobs import enqueue
    print('Publicação enfileirada: ' + enqueue('planilhas', actor='cli'))
